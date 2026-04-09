# Interactive OBO Flow 実装計画書

| 項目                 | 内容                                                                                                   |
| -------------------- | ------------------------------------------------------------------------------------------------------ |
| **作成日**           | 2026-04-07                                                                                             |
| **対象フェーズ**     | Phase 5 (Interactive Flow) — 既存計画書との対応                                                        |
| **前提**             | Phase 3 完了済み（SPA + Autonomous Agent App Flow E2E）                                                |
| **親ドキュメント**   | [実装タスク計画書](app-implementation-plan.md)                                                         |
| **参照ドキュメント** | [Agent OBO OAuth Flow](https://learn.microsoft.com/en-us/entra/agent-id/agent-on-behalf-of-oauth-flow) |

---

## 1. 概要

### 1.1 目的

新しい **「Interactive (OBO)」タブ** を SPA に追加し、**ログインユーザー自身の委任権限（delegated permissions）** で Foundry Hosted Agent を介してリソース API にアクセスする Interactive OBO フローを実現する。

Identity Echo API が `tokenKind: "delegated"` + ログインユーザーの UPN を返すことで、「エージェントが人間ユーザーの権限で API にアクセスした」ことを可視化する。

### 1.2 OBO フローの概要

[公式ドキュメント](https://learn.microsoft.com/en-us/entra/agent-id/agent-on-behalf-of-oauth-flow) に基づくプロトコルステップ:

```text
1. ユーザーがクライアント（SPA）で認証 → Tc を取得 (aud = Blueprint App ID)
2. クライアントが Tc を Agent に渡す
3. Agent Identity Blueprint が MSI で T1 を取得:
     POST /oauth2/v2.0/token
     client_id=Blueprint, scope=api://AzureADTokenExchange/.default,
     fmi_path=AgentIdentity, client_assertion=MSI_Token, grant_type=client_credentials
     → T1
4. Agent Identity が OBO 交換:
     POST /oauth2/v2.0/token
     client_id=AgentIdentity, scope=api://{ResourceAPI}/CallerIdentity.Read,
     client_assertion={T1}, assertion={Tc},
     grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer,
     requested_token_use=on_behalf_of
     → TR (delegated, sub=ユーザー, upn=alice@contoso.com)
5. Agent が TR で Identity Echo API を呼び出す
```

### 1.3 E2E アーキテクチャ

```text
👤 ユーザー (ブラウザ, MSAL ログイン済み)
  │
  ├── MSAL: Tc を取得 (scope = api://{BlueprintId}/access_agent)
  ├── MSAL: Foundry API トークンを取得 (scope = https://ai.azure.com/.default)
  │
  └── Foundry Agent API を直接呼び出し (SPA → Foundry)
        Authorization: Bearer {Foundry API トークン}
        message payload に Tc を metadata として埋め込む
        │
        ▼
  Foundry Hosted Agent
        │
        ├── Step 1: get_t1()  — Project MI → T1 (既存関数)
        ├── Step 2: exchange_interactive_obo(t1, tc) — OBO 交換 → TR (新規)
        └── Step 3: GET /api/resource (Bearer TR) → Identity Echo API
        │
        ▼
  ← SSE streaming → SPA
  ← CallerInfo: { tokenKind: "delegated", upn: "alice@contoso.com" }
```

**設計判断: SPA → Foundry Agent API 直接呼び出し方式を採用**

CORS 検証により Foundry API が `Access-Control-Allow-Origin: *` を返すことを確認済み:

```bash
$ curl -sI -X OPTIONS \
    "https://cogacct-foundry-poc-dev-swec-86d21f.services.ai.azure.com/openai/responses" \
    -H "Origin: http://localhost:5173" \
    -H "Access-Control-Request-Method: POST" \
    -H "Access-Control-Request-Headers: authorization,content-type"

HTTP/2 200
access-control-allow-headers: authorization,content-type
access-control-allow-origin: *
access-control-allow-methods: POST
```

これにより Backend API を経由する必要がなくなり、Interactive Flow は **Autonomous Flow とは異なるアーキテクチャ**（SPA 直接呼び出し）となる。これは Interactive Flow の本質（ユーザーがエージェントを直接呼び出す）に合致している。

**Autonomous Flow との本質的な違い:**

| 観点                     | Autonomous Agent Flow   | Interactive Agent (OBO) Flow |
| ------------------------ | ----------------------- | ---------------------------- |
| Foundry API の呼び出し元 | Backend API（システム） | SPA（ユーザー本人）          |
| 認証トークン             | Backend API の MSI      | ユーザーの Entra ID トークン |
| Tc の要否                | 不要                    | 必要（OBO の起点）           |
| Backend API の役割       | Foundry API プロキシ    | **関与しない**               |

---

## 2. Tc の受け渡しメカニズム

### 2.1 課題

Interactive OBO の Tool (`call_resource_api_interactive_obo`) はユーザーの Tc トークン（JWT 文字列、約1200文字）を必要とするが、LLM にメッセージ本文から長い JWT を正確に抽出させるのは信頼性に欠ける。

### 2.2 実装中に発見した制約

実装時に以下の 2 つの制約が判明した:

1. **metadata 値の 512 文字制限**: Foundry API の `metadata` は各値が最大 512 文字。JWT（~1200文字）を `metadata.user_tc` に直接入れると `400 invalid_payload` エラーになる。
2. **Hosted Agent adapter は `messages=None` で `run()` を呼ぶ**: input の developer メッセージに Tc を埋め込む方式も試したが、adapter は input を内部セッション管理経由で LLM に渡し、`run(messages=None)` で呼び出すため developer メッセージを `run()` 内で取得できない。

### 2.3 採用するアプローチ: metadata 分割格納（チャンキング）

Tc を 500 文字ごとに分割し、`metadata.user_tc_0`, `metadata.user_tc_1`, ... として格納する。`ToolDispatchAgent` が `_request_headers` から `user_tc_N` を連番順に結合して復元する。

```text
[クライアント（SPA / テストスクリプト）]
  # Tc を 500 文字ごとに分割
  metadata = {
    force_tool: "call_resource_api_interactive_obo",
    user_tc_0: tc[0:500],      // 最初の 500 文字
    user_tc_1: tc[500:1000],   // 次の 500 文字
    user_tc_2: tc[1000:],      // 残り
  }
        │
        ▼
[Hosted Agent — ToolDispatchAgent]
  _request_headers から user_tc_0, user_tc_1, ... を読み取り
  → 連番順に結合して Tc を復元
  → request_context.set_user_tc(tc) に保存
        │
        ▼
[Tool — call_resource_api_interactive_obo()]
  tc = request_context.get_user_tc()
  → get_t1() → exchange_interactive_obo(t1, tc) → call API
```

**利点**:

- JWT が LLM を経由しない（改変・切り詰めリスクなし）
- Hosted Agent adapter は single-threaded のため global state が安全
- 既存の `force_tool` パターンの metadata 経路をそのまま使用
- 512 文字制限を回避しつつ、追加インフラ不要

### 2.4 不採用としたアプローチ

| 方式                             | 不採用理由                                               |
| -------------------------------- | -------------------------------------------------------- |
| `metadata.user_tc` に直接格納    | 512 文字制限で `400 invalid_payload`                     |
| developer メッセージに埋め込み   | adapter が `messages=None` で `run()` を呼ぶため取得不可 |
| 外部ストレージ（Blob/Redis）経由 | 追加インフラが必要、オーバーエンジニアリング             |

---

## 3. 変更ファイル一覧

| #                    | ファイル                                                            | 変更種別       | 状態 | 内容                                                                |
| -------------------- | ------------------------------------------------------------------- | -------------- | ---- | ------------------------------------------------------------------- |
| **Entra ID 設定**    |                                                                     |                |      |                                                                     |
| E1                   | Blueprint App Registration                                          | Graph API      | ✅   | `access_agent` スコープ公開、App ID URI 設定                        |
| E1-script            | `src/agent/entra-agent-id/set-blueprint-scope.py`                   | 新規作成       | ✅   | E1 を設定する Graph API スクリプト（冪等、`--delete` 対応）         |
| ~~E2~~               | ~~SPA App Registration — Blueprint 権限~~                           | ~~手動~~       | —    | ~~CLI テストでは不要（動的 consent で通る）。SPA 実装時に再評価~~   |
| E2-admin             | Agent Identity → Resource API Admin Consent                         | Graph API      | ✅   | `AllPrincipals` consent（OBO で任意ユーザーの代理に必要）           |
| E2-admin-script      | `src/agent/entra-agent-id/grant-admin-consent-to-agent-identity.py` | 新規作成       | ✅   | Admin Consent 付与スクリプト（冪等、`--delete` 対応）               |
| E3                   | SPA App Registration                                                | 手動/Terraform | ✅   | `ai.azure.com` API Permission 追加 + Admin Consent 付与             |
| **Agent Runtime**    |                                                                     |                |      |                                                                     |
| A1                   | `src/agent/runtime/auth/token_exchange.py`                          | 関数追加       | ✅   | `exchange_interactive_obo(t1, tc)`                                  |
| A2                   | `src/agent/runtime/tools/interactive_obo.py`                        | 新規作成       | ✅   | `call_resource_api_interactive_obo()` ツール                        |
| A3                   | `src/agent/runtime/request_context.py`                              | 新規作成       | ✅   | `set_user_tc()` / `get_user_tc()`                                   |
| A4                   | `src/agent/runtime/main.py`                                         | 変更           | ✅   | ツール登録 + metadata チャンキングで user_tc を復元・context に保存 |
| **テストスクリプト** |                                                                     |                |      |                                                                     |
| S1                   | `src/agent/scripts/invoke-interactive-agent.py`                     | 新規作成       | ✅   | MSAL で Tc 取得 + metadata 分割 + Agent 呼び出し（E2E テスト済み）  |
| **検査スクリプト**   |                                                                     |                |      |                                                                     |
| S0                   | `src/agent/entra-agent-id/inspect-blueprint.py`                     | 新規作成       | ✅   | Blueprint の現在の設定状態を検査（OBO 前提条件の確認用）            |
| **Frontend SPA**     |                                                                     |                |      |                                                                     |
| F1                   | `src/frontend/src/authConfig.ts`                                    | 変更           | ✅   | Blueprint スコープ + Foundry API スコープ追加                       |
| F2                   | `src/frontend/src/api/foundryAgentApi.ts`                           | 新規作成       | ✅   | SPA → Foundry Agent API 直接呼び出し（SSE + metadata チャンキング） |
| F3                   | `src/frontend/src/components/InteractiveOboPanel.tsx`               | 新規作成       | ✅   | OBO フロー専用チャットパネル（ログイン必須）                        |
| F4                   | `src/frontend/src/App.tsx`                                          | 変更           | ✅   | 「Interactive (OBO)」タブ追加                                       |
| F5                   | `src/frontend/src/utils/extractAgentToolOutput.ts`                  | 変更           | ✅   | OBO フローのステップキー対応                                        |

> **Backend API の変更は不要**: Interactive Flow は SPA → Foundry Agent API 直接呼び出しのため、
> `foundry_client.py` / `routes/call_foundry_agent.py` の変更は不要。

---

## 4. 各ファイルの具体的な実装内容

### 4.1 Entra ID 設定 (E1, E2)

#### E1: Blueprint App Registration — `access_agent` スコープ公開

**なぜ必要か**: OBO フローの Step 4 で `assertion={Tc}` を渡すが、OBO プロトコルは **Tc の `aud` が OBO リクエストの `client_id`（= Blueprint Client ID）と一致すること** を要求する。SPA が `aud=Blueprint` のアクセストークンを MSAL で取得するには、Blueprint に App ID URI と公開スコープが設定されている必要がある。

**公式ドキュメント根拠**:

1. **[Create an agent identity blueprint — Configure identifier URI and scope](https://learn.microsoft.com/en-us/entra/agent-id/create-blueprint?tabs=microsoft-graph-api#configure-identifier-uri-and-scope)** (Entra Agent ID — **最も直接的な根拠**)
   - "If the agents created with the blueprint will support **interactive agents**, where the agent acts on behalf of a user, **your blueprint must expose a scope** so that the agent front end can pass an access token to the agent backend."
   - 公式サンプルコードで `identifierUris`, `oauth2PermissionScopes`, スコープ名 `access_agent` が使用されている
   - 本プロジェクトでは `src/entra_id/api/create-agent-id-blueprint.http` にこの API コールを実装済み

2. **[Agent OAuth flows: On behalf of flow](https://learn.microsoft.com/en-us/entra/agent-id/agent-on-behalf-of-oauth-flow)** (Entra Agent ID)
   - Step 4: `assertion={Tc(aud=AgentIdentity Blueprint, oid=User)}`
   - Step 5: "The OBO protocol requires token audience to match the client ID: **Tc (aud) == Agent identity blueprint client ID**"
   - 冒頭: "Agents have the capabilities of Microsoft Entra ID resource (API) applications and support the API attributes required for the (**OAuth2Permissions**, **AppURI**)."

3. **[Microsoft identity platform and OAuth 2.0 On-Behalf-Of flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow)** (Entra ID 標準 OBO)
   - assertion パラメータ: "This token must have an audience (`aud`) claim of the app making this OBO request (the app denoted by the `client-id` field)."

4. **[Configure an application to expose a web API](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-configure-app-expose-web-apis)** (Entra ID 一般)
   - Application ID URI の設定手順と `oauth2PermissionScopes` の追加手順を記載

Blueprint は Foundry が自動プロビジョニングするため、手動設定または Graph API スクリプトで対応する。

```bash
# Graph API で Blueprint に access_agent スコープを追加
# (src/agent/entra-agent-id/ 配下にスクリプトを作成)

# 1. Blueprint App ID URI を設定
PATCH https://graph.microsoft.com/v1.0/applications/{blueprint_object_id}
{
  "identifierUris": ["api://{blueprint_client_id}"]
}

# 2. access_agent スコープを公開
PATCH https://graph.microsoft.com/v1.0/applications/{blueprint_object_id}
{
  "api": {
    "oauth2PermissionScopes": [
      {
        "id": "{random-uuid}",
        "adminConsentDescription": "Allow the application to access the agent on behalf of the signed-in user",
        "adminConsentDisplayName": "Access Agent",
        "isEnabled": true,
        "type": "User",
        "userConsentDescription": "Allow the application to access the agent on your behalf",
        "userConsentDisplayName": "Access Agent",
        "value": "access_agent"
      }
    ]
  }
}
```

#### E2: ~~SPA App Registration — Blueprint API 権限追加~~ (CLI テストでは不要)

> **実装結果**: CLI テストでは `GRAPH_API_OPS_CLIENT_ID`（「モバイルとデスクトップ」プラットフォーム）で
> Tc を取得したところ、動的 consent が有効で `AADSTS65001` は発生しなかった。
> SPA App Registration は「SPA」プラットフォームのため MSAL Python からトークンを取得すると
> `AADSTS9002327`（cross-origin requests only）になるため、CLI テストには使用できない。
> SPA 実装時に E2 の要否を再評価する。

~~```bash~~
~~# SPA に Blueprint の access_agent 権限を追加~~
~~```~~

#### E2-admin: Agent Identity → Resource API Admin Consent (AllPrincipals)

**新規発見**: OBO 交換で `AADSTS65001` が発生した。Agent Identity が人間ユーザーの代理で
Resource API（Identity Echo API）の `CallerIdentity.Read` にアクセスするには、
**Admin Consent (`consentType: AllPrincipals`)** が必要。

Autonomous Agent User flow の `grant-consent-to-agent-identity.py` は `consentType: Principal`（Agent User 1人のみ）
だったが、OBO では任意の人間ユーザーが対象のため `AllPrincipals` が必要。

**スクリプト**: `src/agent/entra-agent-id/grant-admin-consent-to-agent-identity.py`

```bash
# Admin Consent 付与
python src/agent/entra-agent-id/grant-admin-consent-to-agent-identity.py

# 削除
python src/agent/entra-agent-id/grant-admin-consent-to-agent-identity.py --delete
```

```bash
# Graph API
POST https://graph.microsoft.com/v1.0/oauth2PermissionGrants
{
  "clientId": "{agent_identity_sp_id}",
  "consentType": "AllPrincipals",
  "resourceId": "{resource_api_sp_id}",
  "scope": "CallerIdentity.Read"
}
```

#### E3: SPA App Registration — AI Azure API Permission 追加 ✅

SPA が Foundry Agent API を直接呼び出すため、`https://ai.azure.com/.default` スコープでトークンを取得できるようにする。
services.ai.azure.com エンドポイントは `aud=https://ai.azure.com` のトークンを期待する。

```bash
# Azure Portal > App Registration > API Permissions > Add > APIs my organization uses
# > "AI Azure" (https://ai.azure.com)
# > Delegated: user_impersonation
# Admin Consent を付与
```

**確認ポイント**:

- SPA で `acquireTokenSilent({ scopes: ["api://{BlueprintId}/access_agent"] })` が成功すること
- 取得した Tc の `aud` が Blueprint の Client ID (GUID) と一致すること
- SPA で `acquireTokenSilent({ scopes: ["https://ai.azure.com/.default"] })` が成功すること

---

### 4.2 Agent Runtime — `token_exchange.py` (A1)

`exchange_interactive_obo()` 関数を追加:

```python
def exchange_interactive_obo(t1: str, tc: str) -> dict:
    """Exchange T1 + Tc for TR (delegated resource token) via OBO.

    This is the Interactive OBO flow — the resulting TR is a delegated token
    with the human user as the subject (sub = user OID, upn = user UPN).

    Protocol reference:
    https://learn.microsoft.com/en-us/entra/agent-id/agent-on-behalf-of-oauth-flow

    Args:
        t1: The T1 access token obtained from get_t1().
        tc: The user's access token (aud = Blueprint App ID).

    Returns a dict with keys:
      - "success": bool
      - "access_token": str (TR token, only on success)
      - "claims": dict (decoded TR claims, only on success)
      - "error": str (only on failure)
      - "error_description": str (only on failure)
    """
    payload = {
        "client_id": config.agent_identity_oid,
        "scope": config.resource_api_scope,                # api://{id}/CallerIdentity.Read (delegated)
        "client_assertion_type": _JWT_BEARER,
        "client_assertion": t1,
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": tc,
        "requested_token_use": "on_behalf_of",
    }

    resp = requests.post(_TOKEN_URL, data=payload, timeout=_TIMEOUT)
    body = resp.json()

    if resp.status_code == 200:
        tr = body.get("access_token", "")
        return {
            "success": True,
            "access_token": tr,
            "claims": _decode_jwt_claims(tr) if tr else {},
        }

    return {
        "success": False,
        "error": body.get("error", "unknown"),
        "error_description": body.get("error_description", "N/A"),
        "error_codes": body.get("error_codes", []),
    }
```

---

### 4.3 Agent Runtime — `request_context.py` (A3)

```python
"""Request-scoped context for passing data between ToolDispatchAgent and tools.

The Hosted Agent adapter is single-threaded, so a simple module-level
variable is safe for storing per-request state.
"""

_user_tc: str | None = None


def set_user_tc(tc: str | None) -> None:
    """Store the user's Tc token for the current request."""
    global _user_tc
    _user_tc = tc


def get_user_tc() -> str | None:
    """Retrieve the user's Tc token set by ToolDispatchAgent."""
    return _user_tc
```

---

### 4.4 Agent Runtime — `tools/interactive_obo.py` (A2)

```python
"""Interactive OBO flow tool — T1 + Tc → TR (delegated, human user) → Identity Echo API."""

import json

import requests
from agent_framework import tool
from auth.token_exchange import exchange_interactive_obo, get_t1
from config import config
from request_context import get_user_tc


def _run_interactive_obo() -> str:
    """Implementation of the Interactive OBO flow."""
    result: dict = {
        "name": "call_resource_api_interactive_obo",
        "description": "Call Identity Echo API with Interactive OBO flow (human user delegation).",
        "outputs": {},
        "logs": {
            "step1_get_t1": {},
            "step2_obo_exchange": {},
            "step3_call_resource_api": {},
        },
    }

    # Step 0: Retrieve Tc from request context
    tc = get_user_tc()
    if not tc:
        result["logs"]["step1_get_t1"] = {
            "success": False,
            "error": "no_user_token",
            "error_description": "No user token (Tc) was provided in the request metadata.",
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 1: Get T1 (Blueprint exchange token) — same as other flows
    t1_result = get_t1()
    result["logs"]["step1_get_t1"] = {
        "success": t1_result["success"],
        "claims": t1_result.get("claims") if t1_result["success"] else None,
        "error": t1_result.get("error"),
    }

    if not t1_result["success"]:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 2: OBO exchange — T1 + Tc → TR (delegated, sub = human user)
    tr_result = exchange_interactive_obo(
        t1=t1_result["access_token"],
        tc=tc,
    )
    result["logs"]["step2_obo_exchange"] = {
        "success": tr_result["success"],
        "claims": tr_result.get("claims") if tr_result["success"] else None,
        "error": tr_result.get("error"),
        "error_description": tr_result.get("error_description"),
    }

    if not tr_result["success"]:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 3: Call Identity Echo API with delegated TR
    api_url = f"{config.resource_api_url}/api/resource"
    try:
        resp = requests.get(
            api_url,
            headers={"Authorization": f"Bearer {tr_result['access_token']}"},
            timeout=30,
        )
        result["logs"]["step3_call_resource_api"] = {
            "success": resp.status_code == 200,
            "status_code": resp.status_code,
            "body": resp.json()
            if resp.headers.get("content-type", "").startswith("application/json")
            else resp.text,
        }
        result["outputs"] = (
            resp.json()
            if resp.headers.get("content-type", "").startswith("application/json")
            else {"raw_response": resp.text}
        )
    except Exception as exc:
        result["logs"]["step3_call_resource_api"] = {
            "success": False,
            "error": f"request_exception: {exc}",
        }

    return json.dumps(result, indent=2, ensure_ascii=False)


@tool(
    name="call_resource_api_interactive_obo",
    description="Call Identity Echo API using the Interactive OBO flow (human user delegation).",
)
def call_resource_api_interactive_obo() -> str:
    """Call Identity Echo API using the Interactive OBO flow.

    Performs the OBO token chain:
      1. get_t1()  — Project MI → T1 (Agent Identity token)
      2. exchange_interactive_obo(t1, tc) — T1 + Tc → TR (delegated, sub = human user)
      3. Call Identity Echo API with TR as Bearer token

    The user's Tc token is retrieved from request context (set by ToolDispatchAgent
    from the request metadata, NOT from LLM function arguments).

    Returns:
        A JSON string containing the full logs and outputs of each step.

    JSON format:
        {
            "name": "call_resource_api_interactive_obo",
            "description": "...",
            "outputs": { ... },
            "logs": {
                "step1_get_t1": { ... },
                "step2_obo_exchange": { ... },
                "step3_call_resource_api": { ... }
            }
        }
    """
    return _run_interactive_obo()
```

---

### 4.5 Agent Runtime — `main.py` (A4)

変更点:

```python
# 1. import 追加
from tools.interactive_obo import call_resource_api_interactive_obo
from request_context import set_user_tc

# 2. _TOOL_FUNCS にツール追加
_TOOL_FUNCS = [
    call_resource_api_autonomous_app,
    call_resource_api_autonomous_user,
    call_resource_api_interactive_obo,   # ← 追加
    check_agent_environment,
]

# 3. ToolDispatchAgent.run() 内 — metadata チャンキングで user_tc を復元
class ToolDispatchAgent(Agent):
    def run(self, messages=None, *, stream=False, session=None, tools=None, options=None, **kwargs):
        headers = getattr(self, "_request_headers", {})
        force_tool = headers.get("force_tool")

        # Reassemble user_tc from chunked metadata (user_tc_0, user_tc_1, ...)
        # metadata values are limited to 512 chars, so Tc is split into 500-char chunks.
        tc_chunks = []
        i = 0
        while True:
            chunk = headers.get(f"user_tc_{i}")
            if chunk is None:
                break
            tc_chunks.append(chunk)
            i += 1
        user_tc = "".join(tc_chunks) if tc_chunks else None
        set_user_tc(user_tc)
        # ... 以降は既存の force_tool ディスパッチロジック
```

> **metadata チャンキング方式を採用した理由**:
>
> - `metadata` 値は最大 512 文字。JWT (~1200 文字) を直接入れると `400 invalid_payload`
> - Hosted Agent adapter は `run(messages=None)` で呼ぶため developer メッセージ方式も不可
> - metadata を 500 文字ごとに分割して `user_tc_0`, `user_tc_1`, ... に格納し、`run()` 内で結合して復元する

---

### 4.6 テストスクリプト — `invoke-interactive-agent.py` (S1) ✅ 実装済み

`src/agent/scripts/invoke-interactive-agent.py` — MSAL で Tc を取得し、Foundry Agent API を呼び出す CLI E2E テスト。
Frontend を構築する前に OBO フロー全体を CLI で検証できる。**E2E テスト成功済み**。

実装のポイント:

```python
# --- SPA App Registration の制約 ---
# SPA プラットフォームは MSAL Python から使えない (AADSTS9002327)。
# テスト用に GRAPH_API_OPS_CLIENT_ID (Mobile/Desktop プラットフォーム) を使用。
graph_ops_client_id = _require_env("GRAPH_API_OPS_CLIENT_ID")
app = msal.PublicClientApplication(client_id=graph_ops_client_id, authority=authority)

# --- metadata チャンキング ---
# metadata 値は 512 文字制限 → JWT (~1200 chars) を 500 文字ごとに分割
_CHUNK_SIZE = 500
for i in range(0, len(tc), _CHUNK_SIZE):
    metadata[f"user_tc_{i // _CHUNK_SIZE}"] = tc[i : i + _CHUNK_SIZE]

# developer message 方式は不可 (adapter が messages=None で run() を呼ぶ)
# input_payload = [{"role": "developer", "content": f"__USER_TC__:{tc}"}]  # ← NG

# --- agent_reference ---
extra = {
    "agent_reference": {"name": agent.name, "type": "agent_reference"},
    "metadata": metadata,
}
response = openai_client.responses.create(
    input=input_payload, store=False, extra_body=extra, timeout=180,
)
```

> **実装での発見事項**:
>
> - `ENTRA_SPA_APP_CLIENT_ID` → `GRAPH_API_OPS_CLIENT_ID` に切替（SPA プラットフォーム制約回避）
> - E2 consent (SPA→Blueprint) は CLI テストでは不要だった（動的同意が機能）
> - `model` パラメータ不要（`agent_reference` 使用時は Agent 側で決定）
> - `store=False` 必須（Hosted Agent は session 管理しない）

---

### 4.7 Frontend — `authConfig.ts` (F1) ✅ 実装済み

```typescript
// 追加: Blueprint スコープ（Interactive OBO フロー用 — Tc 取得）
export const blueprintScope = import.meta.env
  .ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID
  ? `api://${import.meta.env.ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID}/access_agent`
  : "";

export const interactiveOboRequest = {
  scopes: [blueprintScope].filter(Boolean),
};

// 追加: Foundry API スコープ（Foundry Agent API 直接呼び出し用）
// services.ai.azure.com エンドポイントは aud=https://ai.azure.com のトークンを期待する
export const foundryApiScope = "https://ai.azure.com/.default";

export const foundryApiRequest = {
  scopes: [foundryApiScope],
};
```

`vite.config.ts` の `envPrefix` には既に `ENTRA_` が含まれるため、`ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID` は追加設定なしで利用可能。

---

### 4.8 Frontend — `foundryAgentApi.ts` (F2) — 新規作成 ✅ 実装済み

SPA から Foundry Agent API を直接呼び出すモジュール。Backend API 経由の `backendApi.ts` とは独立。

```typescript
/**
 * Direct Foundry Agent API client for Interactive OBO flow.
 *
 * Unlike the Autonomous flow (which goes through Backend API),
 * Interactive flow calls Foundry Agent API directly from the browser.
 * CORS is confirmed: Access-Control-Allow-Origin: * on services.ai.azure.com.
 */

import type { StreamCallbacks } from "./backendApi";

const foundryProjectEndpoint = import.meta.env.FOUNDRY_PROJECT_ENDPOINT ?? "";
const foundryAgentName =
  import.meta.env.FOUNDRY_AGENT_NAME ?? "demo-entraagtid-agent";

/**
 * Convert cognitiveservices.azure.com → services.ai.azure.com.
 * Required for Foundry Agent API (agent_reference is not recognized
 * on the cognitiveservices domain).
 */
function toServicesEndpoint(endpoint: string): string {
  return endpoint.replace(
    /\.cognitiveservices\.azure\.com\//,
    ".services.ai.azure.com/",
  );
}

/**
 * Invoke the Foundry Hosted Agent directly from the browser (Interactive OBO flow).
 *
 * @param message      - User's message to the agent
 * @param foundryToken - Bearer token for Foundry API (scope: ai.azure.com/.default)
 * @param tc           - User's Tc token (aud = Blueprint, for OBO exchange)
 * @param callbacks    - SSE stream callbacks (same interface as backendApi.ts)
 * @param forceTool    - Optional tool name to force (e.g. "call_resource_api_interactive_obo")
 */
export function runInteractiveOboStream(
  message: string,
  foundryToken: string,
  tc: string,
  callbacks: StreamCallbacks,
  forceTool?: string,
): AbortController {
  const controller = new AbortController();
  const ctx = { receivedDelta: false };

  const endpoint = toServicesEndpoint(foundryProjectEndpoint);
  // Foundry Responses API endpoint (path-based versioning)
  const url = endpoint.replace(/\/$/, "") + "/openai/v1/responses";

  const metadata: Record<string, string> = {
    // metadata 値は 512 文字制限 → Tc を 500 文字ごとに分割
    ...chunkTc(tc),
  };
  if (forceTool) {
    metadata.force_tool = forceTool;
  }

  const body = {
    input: [{ role: "user", content: message }],
    stream: true,
    store: false,
    agent_reference: {
      name: foundryAgentName,
      type: "agent_reference",
    },
    metadata: {
      // metadata 値は 512 文字制限 → Tc を 500 文字ごとに分割
      ...chunkTc(tc),
      // force_tool はオプション（LLM が自動判断する場合は不要）
    },
  };

  fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${foundryToken}`,
    },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const text = await response.text();
        callbacks.onError(`Foundry API error: ${response.status} — ${text}`);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        callbacks.onError("ReadableStream not supported");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE frames
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          if (!frame.trim()) continue;
          let eventType = "";
          let data = "";
          for (const line of frame.split("\n")) {
            if (line.startsWith("event: ")) eventType = line.slice(7);
            else if (line.startsWith("data: ")) data = line.slice(6);
          }
          if (!data) continue;
          try {
            const parsed = JSON.parse(data);
            handleSSEEvent(eventType, parsed, callbacks, ctx);
          } catch {
            /* skip malformed */
          }
        }
      }
      callbacks.onComplete();
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        callbacks.onError(err.message ?? String(err));
      }
    });

  return controller;
}

// SSE event handler — reuse the same pattern as backendApi.ts
function handleSSEEvent(
  eventType: string,
  data: any,
  callbacks: StreamCallbacks,
  ctx: { receivedDelta: boolean },
): void {
  // ... 同じ SSE ハンドリングロジック（backendApi.ts と同一パターン）
  // response.output_text.delta → onDelta
  // response.output_item.done (function_call_output) → onToolOutput
  // response.completed → onComplete
}
```

> **注**: SSE レスポンスのフォーマットは Foundry API から直接返る場合も OpenAI Responses API 標準に準拠しており、
> `backendApi.ts` で使用している `handleSSEEvent` と同一のパースロジックが使用可能。
> 共通ユーティリティに抽出するか、同一パターンのコピーで実装する。
>
> **metadata チャンキング**: `chunkTc()` ヘルパーは Tc (JWT ~1200 chars) を 500 文字ごとに分割し
> `{ user_tc_0: "...", user_tc_1: "...", user_tc_2: "..." }` の形式でメタデータに格納する。
> Agent 側の `ToolDispatchAgent.run()` で復元する。実装例:
>
> ```typescript
> function chunkTc(tc: string, size = 500): Record<string, string> {
>   const chunks: Record<string, string> = {};
>   for (let i = 0; i < tc.length; i += size) {
>     chunks[`user_tc_${Math.floor(i / size)}`] = tc.slice(i, i + size);
>   }
>   return chunks;
> }
> ```

---

### 4.9 Frontend — `InteractiveOboPanel.tsx` (F3) ✅ 実装済み

`AutonomousChatPanel.tsx` をベースに以下を変更した新コンポーネント:

- **ログイン必須**: 未認証時はサインインを促すメッセージを表示
- **2 トークン取得**: 送信時に Tc（Blueprint scope）と Foundry API トークンの 2 つを MSAL で取得
- **API 呼び出し**: `runInteractiveOboStream(message, foundryToken, tc, callbacks, forceTool?)` — Foundry Agent API 直接
- **ツール選択 UI**: Auto（LLM 自動判断）または明示指定（`force_tool` でメタデータ経由）

```typescript
import { runInteractiveOboStream } from "../api/foundryAgentApi";
import { interactiveOboRequest, foundryApiRequest } from "../authConfig";

const InteractiveOboPanel: React.FC<Props> = ({ onToolOutput, onStreamComplete, onClear }) => {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  // チャット UI (AutonomousChatPanel と同構造)
  // ...

  const handleSend = useCallback(async () => {
    const account = accounts[0];

    // 1. Tc を取得 (Blueprint scope — OBO の入力トークン)
    let tcResponse;
    try {
      tcResponse = await instance.acquireTokenSilent({
        ...interactiveOboRequest,
        account,
      });
    } catch (silentError) {
      tcResponse = await instance.acquireTokenPopup(interactiveOboRequest);
    }

    // 2. Foundry API トークンを取得 (ai.azure.com scope)
    let foundryTokenResponse;
    try {
      foundryTokenResponse = await instance.acquireTokenSilent({
        ...foundryApiRequest,
        account,
      });
    } catch (silentError) {
      foundryTokenResponse = await instance.acquireTokenPopup(foundryApiRequest);
    }

    // 3. Foundry Agent API を直接呼び出し (Tc は metadata に埋め込み)
    const controller = runInteractiveOboStream(
      trimmed,
      foundryTokenResponse.accessToken,  // Authorization: Bearer
      tcResponse.accessToken,             // metadata.user_tc
      {
        onDelta: ...,
        onText: ...,
        onToolOutput: ...,
        onComplete: ...,
        onError: ...,
      },
    );
    abortRef.current = controller;
  }, [instance, accounts, ...]);

  if (!isAuthenticated) {
    return (
      <div className="auth-section">
        <p>Interactive OBO フローを実行するにはサインインしてください。</p>
      </div>
    );
  }

  return (
    // チャット UI (AutonomousChatPanel と同構造)
  );
};
```

---

### 4.10 Frontend — `App.tsx` (F4) ✅ 実装済み

タブを 3 つに変更:

```typescript
type ScenarioTab = "autonomous-agent" | "interactive-obo" | "no-agent";

// タブ UI に Interactive (OBO) タブを追加
<nav className="scenario-tabs">
  <button
    className={`tab ${activeTab === "autonomous-agent" ? "active" : ""}`}
    onClick={() => setActiveTab("autonomous-agent")}
  >
    Autonomous Agent Flow
  </button>
  <button
    className={`tab ${activeTab === "interactive-obo" ? "active" : ""}`}
    onClick={() => setActiveTab("interactive-obo")}
  >
    Interactive Agent (OBO) Flow
  </button>
  <button
    className={`tab ${activeTab === "no-agent" ? "active" : ""}`}
    onClick={() => setActiveTab("no-agent")}
  >
    No Agent Flow (Direct API call)
  </button>
</nav>

{/* Interactive Agent (OBO) Flow — requires login */}
<div style={{ display: activeTab === "interactive-obo" ? undefined : "none" }}>
  {/* リソース API レスポンス + Token Chain の details/summary (既存パターン) */}
  <InteractiveOboPanel
    onToolOutput={handleToolOutput}
    onStreamComplete={handleStreamComplete}
    onClear={handleClear}
  />
</div>
```

---

### 4.11 Frontend — `extractAgentToolOutput.ts` (F5) ✅ 実装済み

OBO フローのステップキー（`step2_obo_exchange`）を認識するように追加:

```typescript
function hasStepKeys(obj: any): boolean {
  if (!obj || typeof obj !== "object") return false;
  return (
    "step1_get_t1" in obj ||
    "step2_exchange_app_token" in obj ||
    "step3_call_resource_api" in obj ||
    // Autonomous Agent User flow keys
    "step2_exchange_user_t2" in obj ||
    "step3_exchange_user_token" in obj ||
    "step4_call_resource_api" in obj ||
    // Interactive OBO flow keys           ← 追加
    "step2_obo_exchange" in obj
  );
}

// isTokenChainSuccess にも OBO パターンを追加
export function isTokenChainSuccess(toolOutput: any): boolean {
  const logs = extractTokenChainLogs(toolOutput);
  if (!logs) return false;

  // Interactive OBO flow (3 steps)
  if (logs.step2_obo_exchange) {
    return (
      logs.step1_get_t1?.success === true &&
      logs.step2_obo_exchange?.success === true &&
      logs.step3_call_resource_api?.success === true
    );
  }

  // ... existing patterns
}
```

---

## 5. 環境変数

### 5.1 新規に必要な環境変数

| 変数名                                     | 設定先          | 値                                                               |
| ------------------------------------------ | --------------- | ---------------------------------------------------------------- |
| `ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID` | Frontend `.env` | Blueprint の Application (Client) ID                             |
| `FOUNDRY_PROJECT_ENDPOINT`                 | Frontend `.env` | Foundry Project Endpoint（Foundry Agent API 直接呼び出しに必要） |
| `FOUNDRY_AGENT_NAME`                       | Frontend `.env` | Hosted Agent 名（デフォルト: `demo-entraagtid-agent`）           |

> `FOUNDRY_PROJECT_ENDPOINT` は Backend API / Agent Runtime 側では既に設定済み。
> Frontend 側にも追加する必要がある。
> `vite.config.ts` の `envPrefix` に `FOUNDRY_` が含まれるため追加設定不要。

### 5.2 `src/.env` への追加例

```env
# Interactive OBO (Phase 5)
ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
FOUNDRY_PROJECT_ENDPOINT=https://cogacct-foundry-poc-dev-swec-86d21f.cognitiveservices.azure.com/api/projects/proj-foundry-poc-dev-swec
FOUNDRY_AGENT_NAME=demo-entraagtid-agent
```

---

## 6. 実装順序（推奨） — 実際の実行順序に更新

```text
Step 1: Entra ID 設定 (E1 + E2-admin)  ✅ 完了
  │   E1: Blueprint にスコープ公開 (set-blueprint-scope.py)
  │   E2-admin: Agent Identity → Resource API に AllPrincipals Admin Consent
  │            (grant-admin-consent-to-agent-identity.py)
  │   ⚠️ E2 (SPA→Blueprint consent) は CLI テストでは不要だった（動的同意で機能）
  │
  ▼
Step 2: Agent Runtime (A1, A2, A3, A4)  ✅ 完了
  │   token_exchange.py + request_context.py + interactive_obo tool + main.py
  │   → Docker build + ACR push + Agent version 更新
  │
  ▼
Step 2.5: テストスクリプト (S1) ★ Frontend 不要の E2E 検証  ✅ 成功
  │   invoke-interactive-agent.py で CLI から OBO フロー全体を検証
  │   → Tc 取得 → Agent → OBO 交換 → Identity Echo API
  │   → tokenKind: "delegated", upn: "shigeyf@agentic-web.cloud" 確認
  │
  ▼
Step 3: Entra ID 設定 (E3)  ✅ 完了
  │   SPA App Registration に ai.azure.com API Permission 追加 + Admin Consent 付与
  │
  ▼
Step 4: Frontend (F1, F2, F3, F4, F5)  ✅ 完了
  │   authConfig (ai.azure.com scope) + foundryAgentApi (metadata chunking) +
  │   InteractiveOboPanel + App.tsx + extractAgentToolOutput
  │
  ▼
Step 5: クラウドデプロイ + E2E 検証  ✅ 完了
      deploy-swa.py → ブラウザ確認
```

> **Backend API の変更・再デプロイは不要**: Interactive Flow は SPA → Foundry 直接のため。

---

## 7. 期待するレスポンス

### 7.1 Identity Echo API レスポンス

```json
{
  "resource": "Demo Protected Resource",
  "accessedAt": "2026-04-07T10:00:00Z",
  "caller": {
    "tokenKind": "delegated",
    "oid": "{ユーザーの Object ID}",
    "upn": "alice@contoso.com",
    "appId": "{Agent Identity の App ID}",
    "scopes": ["CallerIdentity.Read"],
    "roles": []
  },
  "humanReadable": "alice@contoso.com の委任権限 (CallerIdentity.Read) でアクセスされました"
}
```

### 7.2 Token Chain Logs

```json
{
  "step1_get_t1": {
    "success": true,
    "claims": {
      "aud": "api://AzureADTokenExchange の Resource ID",
      "sub": "/eid1/c/pub/t/.../AgentIdentityId",
      "oid": "{Blueprint の SP OID}"
    }
  },
  "step2_obo_exchange": {
    "success": true,
    "claims": {
      "aud": "{Identity Echo API の App ID}",
      "sub": "{ユーザーの Object ID}",
      "upn": "alice@contoso.com",
      "scp": "CallerIdentity.Read",
      "azp": "{Agent Identity の Client ID}"
    }
  },
  "step3_call_resource_api": {
    "success": true,
    "status_code": 200,
    "body": { "caller": { "tokenKind": "delegated", ... } }
  }
}
```

---

## 8. 切り分けポイント — 実際に遭遇した問題を含む

### 8.1 実際に遭遇し解決した問題

| 問題                                                                         | 原因                                                                                              | 解決策                                                                                                                |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **AADSTS9002327** — SPA App Registration で MSAL Python からトークン取得不可 | SPA プラットフォームは `cross-origin requests only` — MSAL Python (ネイティブ) からは使用不可     | テスト用に `GRAPH_API_OPS_CLIENT_ID`（Mobile/Desktop プラットフォーム）を使用。SPA Frontend は MSAL.js なので問題なし |
| **400 invalid_payload** — `metadata.user_tc` に JWT 全体を格納               | metadata 値は最大 512 文字。JWT は ~1200 文字                                                     | 500 文字ごとに `user_tc_0`, `user_tc_1`, ... に分割。Agent 側で `_request_headers` から結合して復元                   |
| **Developer message が Agent に届かない**                                    | Hosted Agent adapter は `run(messages=None)` で呼び出す — input は内部 session 管理に入る         | metadata チャンキング方式を採用（developer message 方式は棄却）                                                       |
| **AADSTS65001** — OBO 交換時に `consent_required`                            | Agent Identity に Resource API への Admin Consent (`AllPrincipals`) がない                        | `grant-admin-consent-to-agent-identity.py` で `consentType: AllPrincipals` の oauth2PermissionGrant を付与            |
| **E2 consent 不要だった**                                                    | `GRAPH_API_OPS_CLIENT_ID` で Tc 取得時、Blueprint `access_agent` scope への動的同意が自動的に機能 | E2 (SPA→Blueprint の事前 consent) は CLI テストでは不要。SPA Frontend では要検証                                      |

### 8.2 今後の切り分けポイント

| 問題                                                        | 原因の候補                                                                                                                                   |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| MSAL で Tc（Blueprint scope）が取得できない                 | Blueprint の App ID URI 未設定、`access_agent` スコープ未公開、SPA の API Permissions 未追加                                                 |
| Tc の `aud` が Blueprint App ID と一致しない                | `accessTokenAcceptedVersion` が 1 の場合 aud が `api://` 形式になる。Blueprint app manifest で `accessTokenAcceptedVersion: 2` に設定        |
| T1 取得は成功するが OBO 交換が失敗する                      | Tc の `aud` ≠ Blueprint client ID、Agent Identity に delegated permission(`CallerIdentity.Read`) が未設定                                    |
| OBO で `AADSTS50013: Assertion failed signature validation` | Tc のトークンが改ざんされている、または不正な署名。metadata 経由で正しく渡されているか確認                                                   |
| TR の `sub` がユーザーの OID にならない                     | OBO ではなく別の grant_type が使われている（`grant_type` パラメータを確認）                                                                  |
| Foundry Agent API が CORS エラー                            | 現時点では `Access-Control-Allow-Origin: *` を確認済みだが、将来のAPI変更で制限される可能性あり。その場合は Backend プロキシにフォールバック |
| Foundry API トークン取得が失敗する                          | SPA App Registration に `ai.azure.com` の API Permission が未追加、Admin Consent 未付与                                                      |
| metadata の user_tc チャンクが Agent に届かない             | Foundry API の `metadata` フォーマット変更。`ToolDispatchAgent` の `_request_headers` keys をログで確認                                      |
| `tokenKind` が `delegated` にならない                       | OBO ではなく別の grant_type が使われている（`grant_type` パラメータを確認）                                                                  |

---

## 9. Autonomous Flow との比較（デモ価値）

Interactive OBO タブが完成し、**3 つのフロー全てを UI で比較可能**になった:

| タブ                  | フロー       | Token Chain                                | Identity Echo API の `tokenKind` | `sub` / `upn`              |
| --------------------- | ------------ | ------------------------------------------ | -------------------------------- | -------------------------- |
| Autonomous Agent      | App Flow     | MI → T1 → TR (client_credentials)          | `app_only`                       | Agent Identity OID         |
| Autonomous Agent      | User Flow    | MI → T1 → T2 → TR (user_fic)               | `delegated`                      | Agent User UPN             |
| **Interactive (OBO)** | **OBO Flow** | **MI → T1, Tc + T1 → TR (jwt-bearer OBO)** | **`delegated`**                  | **ログインユーザーの UPN** |
| No Agent              | Direct       | MSAL → TR (直接)                           | `delegated`                      | ログインユーザーの UPN     |

**Interactive (OBO)** と **No Agent** は同じ `tokenKind` を返すが、**Interactive (OBO) では `appId` が Agent Identity の ID** になる点が異なり、「エージェントが user on behalf of でアクセスした」ことが明確になる。

---

## 10. 実装ログ

### 10.1 E1: Blueprint スコープ設定 ✅

- `set-blueprint-scope.py` で `identifierUris: ["api://{BlueprintClientId}"]` + `access_agent` スコープを設定
- 実行前は `identifierUris: []`, `oauth2Permissions: []` だった (Foundry がプロビジョニングした初期状態)
- `inspect-blueprint.py` で事前・事後の状態を確認

### 10.2 E2-admin: AllPrincipals Admin Consent ✅

- `grant-admin-consent-to-agent-identity.py` で Agent Identity → Resource API に `consentType: AllPrincipals` の `oauth2PermissionGrant` を付与
- これがないと OBO 交換時に `AADSTS65001 consent_required` が発生する
- Autonomous Agent User フローの `consentType: Principal` (単一 Agent User 向け) とは異なり、**任意のユーザー** の委任を許可する

### 10.3 A1-A4: Agent Runtime ✅

- `token_exchange.py`: `exchange_interactive_obo(t1, tc)` 追加 — `grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer`
- `request_context.py`: スレッドセーフな `set_user_tc()` / `get_user_tc()` モジュールレベルグローバル
- `interactive_obo.py`: Step 0 (get Tc from context) → Step 1 (T1) → Step 2 (OBO) → Step 3 (API call)
- `main.py`: metadata チャンキング復元 (`user_tc_0`, `user_tc_1`, ... → 結合 → `set_user_tc()`)
- Docker build + ACR push + Agent version 更新で Hosted Agent にデプロイ

### 10.4 S1: CLI E2E テスト ✅ 成功

`invoke-interactive-agent.py` での E2E テスト結果:

```json
{
  "step1_get_t1": {
    "success": true,
    "token_length": 2548
  },
  "step2_obo_exchange": {
    "success": true,
    "claims": {
      "aud": "api://identity-echo-api-...",
      "sub": "...(user OID)...",
      "upn": "shigeyf@agentic-web.cloud",
      "scp": "CallerIdentity.Read",
      "azp": "6fac9afc-..."
    }
  },
  "step3_call_resource_api": {
    "success": true,
    "status_code": 200,
    "body": {
      "caller": {
        "tokenKind": "delegated",
        "upn": "shigeyf@agentic-web.cloud",
        "appId": "6fac9afc-...",
        "scopes": ["CallerIdentity.Read"],
        "roles": []
      }
    }
  }
}
```

- `tokenKind: "delegated"` — OBO で取得した委任トークン
- `upn: "shigeyf@agentic-web.cloud"` — ログインユーザーの UPN (Agent User ではない)
- `appId: "6fac9afc-..."` — Agent Identity の Client ID (SPA の Client ID ではない)
- `scp: "CallerIdentity.Read"` — Resource API の delegated scope

### 10.5 実装で発見した制約事項

1. **metadata 値の 512 文字制限**: Foundry Hosted Agent の metadata は各値が最大 512 文字。JWT (~1200文字) は分割が必要
2. **Hosted Agent adapter の messages=None**: `run()` は常に `messages=None` で呼ばれる。developer message でデータを渡す方式は不可
3. **SPA プラットフォーム制約**: SPA App Registration は MSAL Python (ネイティブ) から使用不可 (`AADSTS9002327`)
4. **OBO に AllPrincipals consent が必要**: Agent Identity が任意のユーザーを代行するには `consentType: AllPrincipals` が必要
5. **動的同意の挙動**: Mobile/Desktop プラットフォームの App Registration では Blueprint `access_agent` scope への事前 consent (E2) なしで動的同意が機能した
