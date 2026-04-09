# Autonomous Agent User Flow 実装計画書

| 項目                 | 内容                                                                                                                                   |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **作成日**           | 2026-03-27                                                                                                                             |
| **最終更新**         | 2026-04-09                                                                                                                             |
| **対象フェーズ**     | Phase 4 (Autonomous Agent User Flow)                                                                                                   |
| **前提**             | Phase 3 完了済み（SPA + Autonomous Agent App Flow E2E）                                                                                |
| **親ドキュメント**   | [実装タスク計画書](app-implementation-plan.md)                                                                                         |
| **参照ドキュメント** | [Agent User OAuth Flow](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/autonomous-agent-request-agent-user-tokens) |

---

## 1. 概要

### 1.1 目的

Phase 3 の Autonomous Agent App Flow（app-only 権限）に加えて、**Agent User の委任権限（delegated permissions）で動作する Autonomous Agent User Flow** を追加する。

Autonomous Agent App Flow では Agent Identity 自身のアプリケーション権限（`roles`）で API にアクセスしたが、本フローでは **Agent User という専用ユーザーアカウントの委任権限**（`scp`）でアクセスする。Identity Echo API が `tokenKind: "delegated"` + Agent User の UPN を返すことで、「自律エージェントでもユーザーの委任権限で API にアクセスできる」ことを可視化する。

**Autonomous App Flow との本質的な違い:**

| 観点                 | Autonomous Agent App Flow                           | Autonomous Agent User Flow                             |
| -------------------- | --------------------------------------------------- | ------------------------------------------------------ |
| Token Exchange       | T1 → TR（`client_credentials`）                     | T1 → T2 → TR（`user_fic`）                             |
| TR の種別            | app-only（`roles` あり、`scp` なし）                | delegated（`scp` あり、`roles` なし）                  |
| TR の subject        | Agent Identity OID                                  | Agent User OID                                         |
| TR の upn            | なし                                                | Agent User UPN（例: `foundry-agent-user@contoso.com`） |
| 必要な権限種別       | Application Permission（`CallerIdentity.Read.All`） | Delegated Permission（`CallerIdentity.Read`）+ consent |
| ユーザー介在         | 不要                                                | 不要（Agent User は事前作成済み）                      |
| Identity Echo の結果 | `tokenKind: "app_only"`                             | `tokenKind: "delegated"`                               |

### 1.2 user_fic フローのプロトコルステップ

[公式ドキュメント](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/autonomous-agent-request-agent-user-tokens) に基づくプロトコルステップ:

```text
1. Agent が MSI で api://AzureADTokenExchange トークンを取得
2. MSI トークンを client_assertion として T1 を取得:
     POST /oauth2/v2.0/token
     client_id={Blueprint}, scope=api://AzureADTokenExchange/.default,
     fmi_path={AgentIdentity}, client_assertion={MSI_Token}, grant_type=client_credentials
     → T1 (aud=Blueprint)
3. T1 を client_assertion として T2（Agent Identity Exchange Token）を取得:
     POST /oauth2/v2.0/token
     client_id={AgentIdentity}, scope=api://AzureADTokenExchange/.default,
     client_assertion={T1}, grant_type=client_credentials
     → T2 (aud=AgentIdentity)
4. T1 + T2 + Agent User UPN で user_fic grant → TR を取得:
     POST /oauth2/v2.0/token
     client_id={AgentIdentity}, scope=api://{ResourceAPI}/CallerIdentity.Read,
     client_assertion={T1}, user_federated_identity_credential={T2},
     username={AgentUserUPN}, grant_type=user_fic, requested_token_use=on_behalf_of
     → TR (delegated, sub=AgentUser, upn=foundry-agent-user@contoso.com)
5. Agent が TR で Identity Echo API を呼び出す
```

> **注**: `grant_type=user_fic` は OBO (`urn:ietf:params:oauth:grant-type:jwt-bearer`) とは異なる。OBO は人間ユーザーの Tc を assertion として使うが、user_fic は T1 + T2（Agent 内部トークン）のみで Agent User の委任権限を取得する。

### 1.3 E2E アーキテクチャ

```text
👤 ユーザー（ログイン不要）
  │
  └── [チャット送信 + ツール選択: "Autonomous User"]
        │
        ▼
  SPA (AutonomousChatPanel — ツール選択ドロップダウン)
        │ POST /api/demo/autonomous/app/stream
        │ body: { message: "...", force_tool: "call_resource_api_autonomous_user" }
        ▼
  Backend API (MSI 認証 → Foundry Agent API)
        │ metadata: { force_tool: "call_resource_api_autonomous_user" }
        ▼
  Foundry Hosted Agent (ToolDispatchAgent)
        │ force_tool → tools=[call_resource_api_autonomous_user] に制限
        │
        ├── Step 1: get_t1()              — Project MI → T1
        ├── Step 2: exchange_user_t2(t1)  — T1 → T2 (Agent Identity exchange token)
        ├── Step 3: exchange_user_token(t1, t2, username) — T1 + T2 → TR (delegated)
        └── Step 4: GET /api/resource (Bearer TR) → Identity Echo API
        │
        ▼
  ← SSE streaming → SPA
  ← CallerInfo: { tokenKind: "delegated", upn: "foundry-agent-user@contoso.com" }
```

**Autonomous App Flow との共通点:**

SPA → Backend API → Foundry Agent のルーティングは Autonomous App Flow と完全に同一。違いは Agent Runtime 内のトークン交換チェーンのみ。`force_tool` パラメータで Backend API の既存エンドポイントを使い分ける設計を採用した。

---

## 2. Agent User メカニズム

### 2.1 Agent User とは

Agent User は通常の Entra ID ユーザーではなく、Graph API beta の特殊なタイプ `microsoft.graph.agentUser` として作成される。Entra Agent ID 固有の概念であり、以下の特徴を持つ:

- **`identityParentId`**: Agent Identity の Service Principal OID を指定。この Agent User を impersonate できるのは親 Agent Identity のみ
- **通常のユーザーと同じ UPN 形式**: `foundry-agent-user@contoso.com` のような UPN を持ち、delegated token の `upn` claim に反映される
- **パスワードなし**: Agent Identity 経由でのみトークンを取得可能（直接ログイン不可）
- **delegated consent が必要**: Resource API へのアクセスにはこの Agent User に対する oauth2PermissionGrant が必要

### 2.2 user_fic grant type の仕組み

`user_fic` は Entra Agent ID 固有の grant type であり、標準的な OAuth 2.0 フローには存在しない。

**3 ステップのトークン交換チェーン:**

| ステップ | 入力                     | 出力 | grant_type         | 目的                          |
| -------- | ------------------------ | ---- | ------------------ | ----------------------------- |
| Step 1   | MSI token                | T1   | client_credentials | Blueprint → Agent Identity    |
| Step 2   | T1                       | T2   | client_credentials | Agent Identity Exchange Token |
| Step 3   | T1 + T2 + Agent User UPN | TR   | user_fic           | Agent User の委任 TR 取得     |

**Step 2 の HTTP パラメータ:**

```text
POST /oauth2/v2.0/token
client_id             = {agent_identity_oid}                    # Agent Identity の SP OID
scope                 = api://AzureADTokenExchange/.default     # Exchange Token scope
client_assertion_type = urn:ietf:params:oauth:client-assertion-type:jwt-bearer
client_assertion      = {t1}                                    # Step 1 で取得した T1
grant_type            = client_credentials
```

> 返却: T2 (aud = api://AzureADTokenExchange, Agent Identity Exchange Token)

**Step 3 の HTTP パラメータ:**

```text
POST /oauth2/v2.0/token
client_id                          = {agent_identity_oid}
scope                              = api://{ResourceAPI}/CallerIdentity.Read  # delegated スコープ
grant_type                         = user_fic
client_assertion_type              = urn:ietf:params:oauth:client-assertion-type:jwt-bearer
client_assertion                   = {t1}                       # T1（T2 ではない）
user_federated_identity_credential = {t2}                       # Step 2 で取得した T2
username                           = {agent_user_upn}           # Agent User の UPN
requested_token_use                = on_behalf_of
```

> 返却: TR (delegated, sub = Agent User OID, upn = Agent User UPN, scp = CallerIdentity.Read)
>
> **scope の注意点**: `client_credentials` では `/.default` サフィックスが必須だが、`user_fic` では concrete scope（`CallerIdentity.Read`）を指定する。
>
> **設計からの変更点**: 当初 `user_id`（OID）を使用する設計だったが、実装では `username`（UPN）を使用する方式に変更した。Entra ID の user_fic grant は UPN をキーとして Agent User を識別する。

### 2.3 必要な事前設定

user_fic フローが成功するには、以下の 2 つの事前設定が必須:

**1. Agent User の作成**

Graph API beta エンドポイントで `microsoft.graph.agentUser` タイプのユーザーを作成する:

```json
POST https://graph.microsoft.com/beta/users
{
  "@odata.type": "microsoft.graph.agentUser",
  "displayName": "Foundry Agent User",
  "userPrincipalName": "foundry-agent-user@contoso.com",
  "identityParentId": "{Agent Identity SP OID}",
  "mailNickname": "foundry-agent-user",
  "accountEnabled": true
}
```

> `identityParentId` が Agent Identity と Agent User を紐づける。この紐付けにより、Agent Identity のみがこの Agent User を impersonate できる。

**2. Delegated Consent の付与**

Agent Identity が Agent User の代理で Resource API にアクセスするための oauth2PermissionGrant を作成する:

```json
POST https://graph.microsoft.com/v1.0/oauth2PermissionGrants
{
  "clientId": "{Agent Identity SP OID}",
  "consentType": "Principal",
  "principalId": "{Agent User OID}",
  "resourceId": "{Resource API SP OID}",
  "scope": "CallerIdentity.Read"
}
```

> **Interactive OBO Flow との違い**: OBO では `consentType: "AllPrincipals"`（Admin Consent）を使用するが、Agent User Flow では `consentType: "Principal"`（特定ユーザーのみ）で十分。Agent User は 1 名のみであるため、AllPrincipals は不要。

### 2.4 user_fic と OBO の比較

| 観点                  | user_fic (Autonomous User)         | OBO (Interactive)                             |
| --------------------- | ---------------------------------- | --------------------------------------------- |
| **grant_type**        | `user_fic`                         | `urn:ietf:params:oauth:grant-type:jwt-bearer` |
| **Token の起点**      | T1 + T2（Agent 内部）              | T1 + Tc（ユーザーの SPA トークン）            |
| **ユーザー介在**      | 不要                               | 必要（SPA ログイン）                          |
| **対象ユーザー**      | Agent User（事前作成済み）         | ログイン中の人間ユーザー                      |
| **consent 種別**      | `Principal`（Agent User のみ）     | `AllPrincipals`（Admin Consent）              |
| **TR の sub/upn**     | Agent User の OID/UPN              | 人間ユーザーの OID/UPN                        |
| **token chain steps** | 4 steps（T1 → T2 → TR → API call） | 3 steps（T1 → OBO exchange → API call）       |

---

## 3. 変更ファイル一覧

| #                 | ファイル                                                      | 変更種別       | 状態 | 内容                                                                          |
| ----------------- | ------------------------------------------------------------- | -------------- | ---- | ----------------------------------------------------------------------------- |
| **Entra ID 設定** |                                                               |                |      |                                                                               |
| E1                | Agent User                                                    | Graph API      | ✅   | `microsoft.graph.agentUser` タイプのユーザーを作成                            |
| E1-script         | `src/agent/entra-agent-id/create-agent-user.py`               | 新規作成       | ✅   | Agent User 作成スクリプト（冪等、`--delete` 対応）                            |
| E2                | Delegated Consent                                             | Graph API      | ✅   | Agent User に対する `CallerIdentity.Read` の oauth2PermissionGrant            |
| E2-script         | `src/agent/entra-agent-id/grant-consent-to-agent-identity.py` | 新規作成       | ✅   | Consent 付与スクリプト（冪等、`--delete` 対応）                               |
| **Agent Runtime** |                                                               |                |      |                                                                               |
| A1                | `src/agent/runtime/auth/token_exchange.py`                    | 関数追加       | ✅   | `exchange_user_t2(t1)` + `exchange_user_token(t1, t2, username)` — 2 関数追加 |
| A2                | `src/agent/runtime/tools/autonomous_user.py`                  | 新規作成       | ✅   | `call_resource_api_autonomous_user()` ツール                                  |
| A3                | `src/agent/runtime/config.py`                                 | フィールド追加 | ✅   | `agent_user_upn` フィールド（`ENTRA_AGENT_ID_USER_UPN`）                      |
| A4                | `src/agent/agent.yaml`                                        | 変数追加       | ✅   | `ENTRA_AGENT_ID_USER_UPN` 環境変数を追加                                      |
| A5                | `src/agent/runtime/main.py`                                   | ツール登録     | ✅   | `_TOOL_FUNCS` に `call_resource_api_autonomous_user` を追加                   |
| **Backend API**   |                                                               |                |      |                                                                               |
| —                 | （変更なし）                                                  | —              | ✅   | 既存 `force_tool` パラメータで `call_resource_api_autonomous_user` を指定可能 |
| **Frontend SPA**  |                                                               |                |      |                                                                               |
| F1                | `src/frontend/src/components/AutonomousChatPanel.tsx`         | 変更           | ✅   | ツール選択ドロップダウンに「Autonomous User」オプションを追加                 |
| F2                | `src/frontend/src/utils/extractAgentToolOutput.ts`            | 変更           | ✅   | User フロー（4 ステップ）のステップキー対応                                   |

> **Backend API の変更は不要**: Autonomous User Flow は既存の `POST /api/demo/autonomous/app` エンドポイントの `force_tool` パラメータを使用する。当初計画では `POST /api/demo/autonomous/user` を追加する設計だったが、`force_tool` パターンが十分に汎用的であるため、専用エンドポイントは不要と判断した。

---

## 4. 各ファイルの具体的な実装内容

### 4.1 Entra ID 設定 (E1, E2)

#### E1: Agent User の作成

**なぜ必要か**: user_fic grant type は `username` パラメータで指定されたユーザーの代理としてトークンを取得する。このユーザーは事前に Entra ID テナントに存在している必要がある。通常のユーザー（人間）ではなく、`microsoft.graph.agentUser` タイプの専用ユーザーを作成する。

**公式ドキュメント根拠**:

1. **[Request tokens for agent users](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/autonomous-agent-request-agent-user-tokens)** — "Create an agent user" セクション:
   - "Agent users are a special type of user account in Microsoft Entra ID that can only be impersonated by a specific agent identity."
   - `@odata.type: "microsoft.graph.agentUser"` + `identityParentId` が必須

**スクリプト**: `src/agent/entra-agent-id/create-agent-user.py`

```bash
# Agent User 作成
python src/agent/entra-agent-id/create-agent-user.py

# 削除
python src/agent/entra-agent-id/create-agent-user.py --delete
```

```python
# 必要な Graph API 権限 (MSAL interactive flow):
scopes = [
    "AgentIdentityBlueprint.Create",
    "AgentIdentityBlueprint.AddRemoveCreds.All",
    "AgentIdentityBlueprint.ReadWrite.All",
    "AgentIdentityBlueprintPrincipal.Create",
    "AgentIdentity.ReadWrite.All",
    "DelegatedPermissionGrant.ReadWrite.All",
    "User.ReadWrite.All",
]

# Graph API beta endpoint
body = {
    "@odata.type": "microsoft.graph.agentUser",
    "displayName": display_name,                    # 例: "Foundry Agent User"
    "userPrincipalName": upn,                       # 例: "foundry-agent-user@contoso.com"
    "identityParentId": agent_identity_sp_id,       # Agent Identity の SP OID
    "mailNickname": mail_nickname,                  # UPN の @ 前部分
    "accountEnabled": True,
}
resp = requests.post(f"{GRAPH_BASE}/users", headers=headers, json=body)
```

**冪等性**: `displayName` で既存ユーザーを検索し、存在する場合はスキップ。

#### E2: Delegated Consent の付与

**なぜ必要か**: user_fic の Step 3 で Agent Identity が Agent User の代理として Resource API の delegated scope（`CallerIdentity.Read`）にアクセスするため、事前に oauth2PermissionGrant が必要。これがないと `AADSTS65001` (invalid_grant) エラーが発生する。

**公式ドキュメント根拠**:

1. **[Grant consent to agent identity](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/autonomous-agent-request-agent-user-tokens?tabs=rest#grant-consent-to-agent-identity)** — "The agent identity needs to be granted consent to access the resource API on behalf of the agent user."

**スクリプト**: `src/agent/entra-agent-id/grant-consent-to-agent-identity.py`

```bash
# Consent 付与
python src/agent/entra-agent-id/grant-consent-to-agent-identity.py

# 取り消し
python src/agent/entra-agent-id/grant-consent-to-agent-identity.py --delete
```

```python
# 必要な Graph API 権限:
scopes = [
    "DelegatedPermissionGrant.ReadWrite.All",
    "Application.Read.All",
    "User.Read.All",
]

# Graph API v1.0
body = {
    "clientId": agent_identity_id,        # Agent Identity SP OID
    "consentType": "Principal",           # 特定ユーザー（Agent User）のみ
    "principalId": agent_user_id,         # Agent User OID
    "resourceId": resource_sp_id,         # Resource API SP OID
    "scope": scope_name,                  # "CallerIdentity.Read"
}
resp = requests.post(f"{GRAPH_BASE}/oauth2PermissionGrants", headers=headers, json=body)
```

**冪等性**: 既存の grant を検索し、scope が不足している場合のみ PATCH で追加。完全一致の場合はスキップ。

---

### 4.2 Agent Runtime — `token_exchange.py` (A1)

Phase 3 で実装済みの `get_t1()` に加え、2 つの関数を追加:

#### `exchange_user_t2()` — T2（Agent Identity Exchange Token）取得

```python
def exchange_user_t2(t1: str) -> dict:
    """Exchange T1 for T2 (Agent Identity exchange token) using client_credentials.

    This is Step 2 of the Autonomous User flow.
    Entra ID validates that T1.aud == Agent Identity Blueprint.

    Args:
        t1: The T1 access token obtained from get_t1().

    Returns a dict with keys:
      - "success": bool
      - "access_token": str (T2 token, only on success)
      - "claims": dict (decoded T2 claims, only on success)
      - "error": str (only on failure)
      - "error_description": str (only on failure)
    """
    payload = {
        "client_id": config.agent_identity_oid,
        "scope": _TOKEN_EXCHANGE_SCOPE,          # api://AzureADTokenExchange/.default
        "client_assertion_type": _JWT_BEARER,
        "client_assertion": t1,
        "grant_type": "client_credentials",
    }

    resp = requests.post(_TOKEN_URL, data=payload, timeout=_TIMEOUT)
    body = resp.json()

    if resp.status_code == 200:
        t2 = body.get("access_token", "")
        return {
            "success": True,
            "access_token": t2,
            "claims": _decode_jwt_claims(t2) if t2 else {},
        }

    return {
        "success": False,
        "error": body.get("error", "unknown"),
        "error_description": body.get("error_description", "N/A"),
        "error_codes": body.get("error_codes", []),
    }
```

> **ポイント**: `client_id` は `agent_identity_oid`（Agent Identity の SP OID）。T1 を client_assertion として、Agent Identity 自身の Exchange Token を取得する。

#### `exchange_user_token()` — TR（Delegated Resource Token）取得

```python
def exchange_user_token(t1: str, t2: str, username: str) -> dict:
    """Exchange T1 + T2 for TR (delegated resource token) via user_fic grant.

    This is Step 3 of the Autonomous User flow (Agent User Impersonation).
    Uses the ``user_fic`` grant type with ``user_federated_identity_credential``
    as defined in the official Entra Agent ID protocol.

    The resulting TR is a **delegated** token with the Agent User as the subject.

    Args:
        t1: The T1 access token (client_assertion).
        t2: The T2 access token (user_federated_identity_credential).
        username: The Agent User UPN (e.g. foundry-agent-user@contoso.com).
    """
    payload = {
        "client_id": config.agent_identity_oid,
        "scope": config.resource_api_scope,                 # api://{id}/CallerIdentity.Read
        "grant_type": "user_fic",
        "client_assertion_type": _JWT_BEARER,
        "client_assertion": t1,
        "user_federated_identity_credential": t2,
        "username": username,
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

> **注**: `scope` には concrete scope（`CallerIdentity.Read`）を指定する。`client_credentials` では `/.default` が必須だが、`user_fic` では concrete scope を使用。`requested_token_use=on_behalf_of` は必須パラメータ。

---

### 4.3 Agent Runtime — `tools/autonomous_user.py` (A2)

4 ステップの Token Chain を実行するツール:

```python
"""Autonomous Agent (User) flow tool — T1 → T2 → TR (delegated) → Identity Echo API."""

import json
import requests
from agent_framework import tool
from auth.token_exchange import exchange_user_t2, exchange_user_token, get_t1
from config import config


def _run_autonomous_user() -> str:
    """Implementation of the Autonomous Agent (User) flow."""
    result: dict = {
        "name": "call_resource_api_autonomous_user",
        "description": "Call Identity Echo API with Agent Identity Autonomous Agent (User) flow.",
        "outputs": {},
        "logs": {
            "step1_get_t1": {},
            "step2_exchange_user_t2": {},
            "step3_exchange_user_token": {},
            "step4_call_resource_api": {},
        },
    }

    # Step 1: Get T1 (Blueprint exchange token)
    t1_result = get_t1()
    result["logs"]["step1_get_t1"] = {
        "success": t1_result["success"],
        "claims": t1_result.get("claims") if t1_result["success"] else None,
        "error": t1_result.get("error"),
    }
    if not t1_result["success"]:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 2: Exchange T1 → T2 (Agent Identity exchange token)
    t2_result = exchange_user_t2(t1_result["access_token"])
    result["logs"]["step2_exchange_user_t2"] = {
        "success": t2_result["success"],
        "claims": t2_result.get("claims") if t2_result["success"] else None,
        "error": t2_result.get("error"),
        "error_description": t2_result.get("error_description"),
    }
    if not t2_result["success"]:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 3: Exchange T1 + T2 → TR (delegated resource token, Agent User)
    tr_result = exchange_user_token(
        t1=t1_result["access_token"],
        t2=t2_result["access_token"],
        username=config.agent_user_upn,
    )
    result["logs"]["step3_exchange_user_token"] = {
        "success": tr_result["success"],
        "claims": tr_result.get("claims") if tr_result["success"] else None,
        "error": tr_result.get("error"),
        "error_description": tr_result.get("error_description"),
    }
    if not tr_result["success"]:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 4: Call Identity Echo API with delegated TR
    api_url = f"{config.resource_api_url}/api/resource"
    try:
        resp = requests.get(
            api_url,
            headers={"Authorization": f"Bearer {tr_result['access_token']}"},
            timeout=30,
        )
        result["logs"]["step4_call_resource_api"] = {
            "success": resp.status_code == 200,
            "status_code": resp.status_code,
            "body": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
        }
        result["outputs"] = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw_response": resp.text}
    except Exception as exc:
        result["logs"]["step4_call_resource_api"] = {
            "success": False,
            "error": f"request_exception: {exc}",
        }

    return json.dumps(result, indent=2, ensure_ascii=False)


@tool(
    name="call_resource_api_autonomous_user",
    description="Call Identity Echo API using the Agent Identity Autonomous Agent (User) flow.",
)
def call_resource_api_autonomous_user() -> str:
    """Call Identity Echo API using the Agent Identity Autonomous User flow.

    Performs the full credential chaining (3-step token acquisition):
      1. get_t1()              — Project MI → T1 (Blueprint exchange token)
      2. exchange_user_t2(t1)  — T1 → T2 (Agent Identity exchange token)
      3. exchange_user_token(t1, t2, username) — T1 + T2 → TR (delegated, Agent User)
      4. Call Identity Echo API with TR as Bearer token
    """
    return _run_autonomous_user()
```

**出力 JSON フォーマット:**

```json
{
  "name": "call_resource_api_autonomous_user",
  "outputs": {
    "caller": {
      "tokenKind": "delegated",
      "oid": "{Agent User OID}",
      "upn": "foundry-agent-user@contoso.com",
      "scopes": ["CallerIdentity.Read"]
    },
    "humanReadable": "foundry-agent-user@contoso.com の委任権限 (CallerIdentity.Read) でアクセスされました"
  },
  "logs": {
    "step1_get_t1": { "success": true, "claims": { "oid": "...", "sub": "..." } },
    "step2_exchange_user_t2": { "success": true, "claims": { "aud": "api://AzureADTokenExchange" } },
    "step3_exchange_user_token": { "success": true, "claims": { "sub": "...", "upn": "foundry-agent-user@contoso.com", "scp": "CallerIdentity.Read" } },
    "step4_call_resource_api": { "success": true, "status_code": 200, "body": { "caller": { ... } } }
  }
}
```

> **Autonomous App Flow との構造的差異**: App Flow は 3 ステップ（step1/step2/step3）、User Flow は 4 ステップ（step1/step2/step3/step4）。Frontend の `extractAgentToolOutput.ts` はステップキーの存在で自動判別する。

---

### 4.4 Agent Runtime — `config.py` (A3) ✅ 変更済み

```python
@dataclass(frozen=True)
class AgentConfig:
    """Environment variables for the Foundry Hosted Agent."""

    # ... 既存フィールド ...

    # Phase 4: Autonomous Agent User Flow
    agent_user_upn: str = field(
        default_factory=lambda: _require_env("ENTRA_AGENT_ID_USER_UPN")
    )
```

> **設計からの変更点**: 当初は `AGENT_USER_OID` 環境変数で Agent User の OID を使用する計画だったが、user_fic grant は `username`（UPN）パラメータを使用するため、`ENTRA_AGENT_ID_USER_UPN` のみで動作する。`AGENT_USER_OID` は不要。

---

### 4.5 Agent Runtime — `agent.yaml` (A4) ✅ 変更済み

```yaml
name: demo-entraagtid-agent
definition:
  # ... 既存設定 ...
  environment_variables:
    # ... 既存変数 ...
    ENTRA_AGENT_ID_USER_UPN: ${ENTRA_AGENT_ID_USER_UPN}
```

> Agent version 再作成時にこの環境変数がコンテナに注入される。

---

### 4.6 Agent Runtime — `main.py` (A5) ✅ 変更済み

```python
from tools.autonomous_user import call_resource_api_autonomous_user

_TOOL_FUNCS = [
    call_resource_api_autonomous_app,
    call_resource_api_autonomous_user,    # ← Phase 4 で追加
    call_resource_api_interactive_obo,
    check_agent_environment,
]
```

`ToolDispatchAgent` の `force_tool` メタデータで `call_resource_api_autonomous_user` を指定すると、`tools=[call_resource_api_autonomous_user]` のみで `super().run()` が呼ばれ、LLM は必ずこのツールを呼び出す。

---

### 4.7 Backend API — 既存 `force_tool` パターンの活用

Backend API のコード変更は不要。Phase 3 で実装済みの `POST /api/demo/autonomous/app` エンドポイントの `force_tool` パラメータを使用:

```json
POST /api/demo/autonomous/app/stream
{
  "message": "Call the resource API using the autonomous user flow.",
  "force_tool": "call_resource_api_autonomous_user"
}
```

`foundry_client.py` の `invoke_agent_stream()` が `metadata.force_tool` として Agent に転送し、`ToolDispatchAgent.run()` がツール制限を適用する。

> **当初の設計との変更点**: 計画では `POST /api/demo/autonomous/user` を追加する予定だったが、`force_tool` パターンが Autonomous App・Autonomous User・Debug の 3 フローを 1 エンドポイントで扱えるため、専用エンドポイントは不要と判断した。

---

### 4.8 Frontend SPA — `AutonomousChatPanel.tsx` (F1) ✅ 変更済み

ツール選択ドロップダウンに「Autonomous User」オプションを追加:

```typescript
const TOOL_OPTIONS = [
  { label: "Auto (LLM が判断)", value: "" },
  {
    label: "Autonomous App (agent_app)",
    value: "call_resource_api_autonomous_app",
  },
  {
    label: "Autonomous User (agent_user)",
    value: "call_resource_api_autonomous_user",
  },
  { label: "Check Environment (debug)", value: "check_agent_environment" },
];
```

選択されたツールの `value` が `runAutonomousAppStream()` の `forceTool` パラメータとして渡され、Backend API → Agent の `metadata.force_tool` に伝搬する。

> **当初の設計との変更点**: 計画では `demoApi.ts` + `ScenarioPanel.tsx` を追加する設計だったが、既存の `AutonomousChatPanel` にツール選択ドロップダウンを追加する方式が、コード重複なしで全フローをカバーできるため採用した。

---

### 4.9 Frontend SPA — `extractAgentToolOutput.ts` (F2) ✅ 変更済み

Autonomous User Flow の 4 ステップに対応するキー判定を追加:

```typescript
function hasStepKeys(obj: any): boolean {
  if (!obj || typeof obj !== "object") return false;
  return (
    "step1_get_t1" in obj ||
    "step2_exchange_app_token" in obj || // Autonomous App flow
    "step3_call_resource_api" in obj ||
    // Autonomous User flow keys — Phase 4 で追加
    "step2_exchange_user_t2" in obj ||
    "step3_exchange_user_token" in obj ||
    "step4_call_resource_api" in obj ||
    // Interactive OBO flow keys — Phase 5 で追加
    "step2_obo_exchange" in obj
  );
}

export function isTokenChainSuccess(toolOutput: any): boolean {
  const logs = extractTokenChainLogs(toolOutput);
  if (!logs) return false;

  // Autonomous User flow (4 steps)
  if (logs.step2_exchange_user_t2) {
    return (
      logs.step1_get_t1?.success === true &&
      logs.step2_exchange_user_t2?.success === true &&
      logs.step3_exchange_user_token?.success === true &&
      logs.step4_call_resource_api?.success === true
    );
  }

  // Autonomous App flow (3 steps)
  return (
    logs.step1_get_t1?.success === true &&
    logs.step2_exchange_app_token?.success === true &&
    logs.step3_call_resource_api?.success === true
  );
}
```

> **フロー自動判別**: `step2_exchange_user_t2` キーの存在で Autonomous User Flow と判別。App Flow の `step2_exchange_app_token` / OBO Flow の `step2_obo_exchange` とは異なるキー名のため、追加のフラグは不要。

---

## 5. 環境変数

### 5.1 新規に必要な環境変数

| 変数名                    | 設定先                     | 値                                                        | 備考                                        |
| ------------------------- | -------------------------- | --------------------------------------------------------- | ------------------------------------------- |
| `ENTRA_AGENT_ID_USER_UPN` | Agent Runtime `agent.yaml` | Agent User の UPN（例: `foundry-agent-user@contoso.com`） | user_fic の `username` パラメータとして使用 |

### 5.2 Agent User 作成スクリプトが参照する環境変数

| 変数名                             | 設定先     | 値                                    |
| ---------------------------------- | ---------- | ------------------------------------- |
| `ENTRA_TENANT_ID`                  | `src/.env` | テナント ID                           |
| `ENTRA_AGENT_IDENTITY_CLIENT_ID`   | `src/.env` | Agent Identity の SP OID              |
| `ENTRA_AGENT_ID_USER_DISPLAY_NAME` | `src/.env` | Agent User の表示名                   |
| `ENTRA_AGENT_ID_USER_UPN`          | `src/.env` | Agent User の UPN                     |
| `GRAPH_API_OPS_CLIENT_ID`          | `src/.env` | Graph API 操作用 Public Client App ID |

### 5.3 Consent 付与スクリプトが参照する環境変数

| 変数名                             | 設定先     | 値                                                     |
| ---------------------------------- | ---------- | ------------------------------------------------------ |
| `ENTRA_AGENT_IDENTITY_CLIENT_ID`   | `src/.env` | Agent Identity の SP OID                               |
| `ENTRA_AGENT_ID_USER_DISPLAY_NAME` | `src/.env` | Agent User の表示名                                    |
| `ENTRA_RESOURCE_API_CLIENT_ID`     | `src/.env` | Resource API の Application (Client) ID                |
| `ENTRA_RESOURCE_API_SCOPE`         | `src/.env` | Delegated scope（例: `api://.../CallerIdentity.Read`） |
| `GRAPH_API_OPS_CLIENT_ID`          | `src/.env` | Graph API 操作用 Public Client App ID                  |

---

## 6. 実装チェックリスト（実施済み）

### (1) Entra ID 設定 — Agent User セットアップ

- [x] Agent User を作成 — ✅ `create-agent-user.py` 実行済み
- [x] `CallerIdentity.Read`（Delegated）に対して Agent User の同意を付与 — ✅ `grant-consent-to-agent-identity.py` 実行済み

### (2) Hosted Agent の変更（`src/agent/runtime/`）

- [x] `token_exchange.py` に `exchange_user_t2(t1)` と `exchange_user_token(t1, t2, username)` を追加 — ✅ 実装済み
- [x] `tools/autonomous_user.py` を新規作成（`@tool` デコレータ） — ✅ 実装済み
- [x] `config.py` に `agent_user_upn` フィールドを追加 — ✅ `_require_env("ENTRA_AGENT_ID_USER_UPN")` で定義
- [x] `agent.yaml` に `ENTRA_AGENT_ID_USER_UPN` を追加 — ✅ 追加済み
- [x] `main.py` に `call_resource_api_autonomous_user` を登録 — ✅ `_TOOL_FUNCS` に追加済み

### (3) Backend API

- [x] 既存 `force_tool` パラメータで対応 — ✅ 専用エンドポイント追加不要

### (4) Frontend SPA

- [x] `AutonomousChatPanel.tsx` にツール選択ドロップダウン追加 — ✅ Auto / App / **User** / Debug
- [x] `extractAgentToolOutput.ts` に User フローの 4 ステップキー判定追加 — ✅ 実装済み

### (5) E2E 動作確認

- [x] `force_tool=call_resource_api_autonomous_user` → `tokenKind: "delegated"`, `upn: "foundry-agent-user@..."` を確認 — ✅ E2E 確認済み

### 切り分けポイント

| 問題                                 | 原因の候補                                                                         |
| ------------------------------------ | ---------------------------------------------------------------------------------- |
| Agent User FIC（user_fic）が失敗する | Agent User への delegated consent が未設定（`AADSTS65001`）                        |
| `tokenKind` が `app_only` になる     | `grant_type` が `client_credentials` になっている（user_fic パラメータの設定漏れ） |
| `upn` が Agent User のものにならない | `username` パラメータの値が Agent User の UPN と一致しない                         |
| T2 取得が失敗する                    | T1 が無効、または Agent Identity OID（`client_id`）が正しくない                    |
| E2E でタイムアウトする               | Agent version の再デプロイが必要（新しい環境変数を反映するため）                   |

---
