# Autonomous Agent App Flow 実装計画書

| 項目                 | 内容                                                                                                      |
| -------------------- | --------------------------------------------------------------------------------------------------------- |
| **作成日**           | 2026-03-27                                                                                                |
| **最終更新**         | 2026-04-09                                                                                                |
| **対象フェーズ**     | Phase 2 (Hosted Agent 最小実装) + Phase 3 (SPA 統合 E2E)                                                  |
| **前提**             | Phase 1 完了済み（SPA + Identity Echo API）                                                               |
| **親ドキュメント**   | [実装タスク計画書](app-implementation-plan.md)                                                            |
| **参照ドキュメント** | [Agent Identity concepts](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-identity) |

---

## 1. 概要

### 1.1 目的

Foundry Hosted Agent を構築し、**Agent Identity のアプリケーション権限（app-only token）で Identity Echo API にアクセスする** Autonomous Agent App Flow を実現する。

これは本プロジェクトで最初に Entra Agent ID を実証するフローであり、以下の 2 つのフェーズで段階的に構築する:

- **Phase 2**: Foundry Hosted Agent の最小実装 — T1/TR Token Exchange + Identity Echo API 呼び出し
- **Phase 3**: SPA + Backend API を統合し、ブラウザから E2E でフローを実行

Identity Echo API が `tokenKind: "app_only"` + Agent Identity の OID を返すことで、「エージェントが自身の権限で API にアクセスした」ことを可視化する。

### 1.2 App Flow のプロトコルステップ

[Agent Identity concepts](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-identity) に基づくプロトコルステップ:

```text
1. Agent が MSI で api://AzureADTokenExchange トークンを取得:
     DefaultAzureCredential().get_token("api://AzureADTokenExchange/.default")
     → MSI token (aud=api://AzureADTokenExchange, oid=Project MI OID)
2. MSI トークンを client_assertion として T1 を取得:
     POST /oauth2/v2.0/token
     client_id={Blueprint}, scope=api://AzureADTokenExchange/.default,
     fmi_path={AgentIdentity}, client_assertion={MSI_Token}, grant_type=client_credentials
     → T1 (aud=api://AzureADTokenExchange, sub=Agent Identity)
3. T1 を client_assertion として TR を取得 (client_credentials):
     POST /oauth2/v2.0/token
     client_id={AgentIdentity}, scope=api://{ResourceAPI}/.default,
     client_assertion={T1}, grant_type=client_credentials
     → TR (app-only, roles=["CallerIdentity.Read.All"], sub=Agent Identity OID)
4. Agent が TR で Identity Echo API を呼び出す:
     GET /api/resource
     Authorization: Bearer {TR}
     → { "caller": { "tokenKind": "app_only", "oid": "...", "roles": [...] } }
```

> **注**: `client_credentials` grant type では scope に `/.default` サフィックスが必須。具体スコープ名（`CallerIdentity.Read.All`）を直接指定すると Entra ID がエラーを返す。Delegated フロー（Interactive / Autonomous Agent User）では具体スコープ `api://{id}/CallerIdentity.Read` を指定する。

### 1.3 E2E アーキテクチャ

**Phase 2（Agent 単体テスト）:**

```text
🧪 テスター（curl / invoke-agent.py）
  │
  └── POST /api/demo/autonomous/app → Backend API
        │ MSI 認証 → Foundry Agent API (agent_reference)
        ▼
  Foundry Hosted Agent
        │
        ├── Step 1: get_t1()            — Project MI → T1 (Agent Identity token)
        ├── Step 2: exchange_app_token() — T1 → TR (app-only resource token)
        └── Step 3: GET /api/resource (Bearer TR) → Identity Echo API
        │
        ▼
  ← { "caller": { "tokenKind": "app_only", "oid": "6fac9afc-...", "roles": ["CallerIdentity.Read.All"] } }
```

**Phase 3（SPA 統合 E2E）:**

```text
👤 ユーザー（ログイン不要）
  │
  └── [チャット送信] → SPA (AutonomousChatPanel)
        │ POST /api/demo/autonomous/app/stream
        ▼
  Backend API (MSI 認証 → Foundry Agent API, SSE streaming)
        │ metadata: { force_tool: "call_resource_api_autonomous_app" }  ← オプション
        ▼
  Foundry Hosted Agent (ToolDispatchAgent)
        │
        ├── Step 1: get_t1()           — Project MI → T1
        ├── Step 2: exchange_app_token() — T1 → TR (app-only)
        └── Step 3: GET /api/resource (Bearer TR) → Identity Echo API
        │
        ▼
  ← SSE events: response.created → function_call → function_call_output
     → output_text.delta (逐次) → response.completed
  ← SPA: テキストデルタをリアルタイム表示 + ツール出力を JSON で折りたたみ表示
  ← CallerInfo: { tokenKind: "app_only", oid: "6fac9afc-..." }
```

**他のフローとの比較:**

| 観点                     | Autonomous Agent App Flow    | Autonomous Agent User Flow | Interactive Agent (OBO) Flow |
| ------------------------ | ---------------------------- | -------------------------- | ---------------------------- |
| Foundry API の呼び出し元 | Backend API（システム）      | Backend API（システム）    | SPA（ユーザー本人）          |
| 認証トークン             | Backend API の MSI           | Backend API の MSI         | ユーザーの Entra ID トークン |
| Token Exchange           | T1 → TR (client_credentials) | T1 → T2 → TR (user_fic)    | T1 + Tc → TR (OBO)           |
| TR の種別                | app-only (`roles`)           | delegated (`scp`)          | delegated (`scp`)            |
| Identity Echo の結果     | `tokenKind: "app_only"`      | `tokenKind: "delegated"`   | `tokenKind: "delegated"`     |

---

## 2. FIC（Federated Identity Credential）メカニズム

### 2.1 課題: DefaultAzureCredential と Agent Identity の分離

Foundry Hosted Agent のコンテナ内で `DefaultAzureCredential()` が返すのは **Project MI**（Foundry Project の System-Assigned Managed Identity）のトークンであり、Agent Identity のトークンではない。T1 を取得するには、MI トークンを `client_assertion` として Blueprint に提示し、FIC（Federated Identity Credential）の検証を経て T1 トークンを取得する必要がある。

| Identity           | Application ID (appid)                | Object ID (oid)                    | 用途                                                               |
| ------------------ | ------------------------------------- | ---------------------------------- | ------------------------------------------------------------------ |
| **Project MI**     | Foundry Project の System-Assigned MI | (MI の Service Principal OID)      | `DefaultAzureCredential()` が返す。ACR Pull、Azure Management など |
| **Agent Identity** | Blueprint の Application (Client) ID  | Blueprint の Service Principal OID | T1 トークンの subject。Identity Echo API へのアクセス主体          |

### 2.2 実装中に発見した制約

Foundry が Blueprint に自動プロビジョニングする FIC は **1 つのみ**であり、その subject は Azure Machine Learning の内部 FMI パス（`/eid1/c/pub/t/{tenantId}/a/{AML_AppID}/AzureAI/FMI`）である。この FIC は Agent Service の内部インフラ（MCP ツール認証等）のために Azure ML の First-Party App が使用するものであり、**Hosted Agent コンテナ内のユーザーコードからは利用できない**。

```text
既定 FIC (Foundry 自動プロビジョニング):
  subject: /eid1/c/pub/t/{tenantId_b64}/a/{AML_AppID_b64}/AzureAI/FMI
  → Azure Machine Learning First-Party App の内部 FMI 専用
  → Hosted Agent 内のユーザーコードからは使用不可

DefaultAzureCredential().get_token() の oid:
  → Project MI の Object ID（既定 FIC の subject とは一致しない）
  → AADSTS700213: No matching federated identity record found
```

### 2.3 採用するアプローチ: Blueprint に Project MI 用の FIC を手動登録

Blueprint に Project MI 用の FIC を手動で登録し、MI トークンの `oid` と FIC の `subject` を一致させる:

```text
手動登録した FIC:
  subject:  {Project MI の Object ID}  ← DefaultAzureCredential() が返すトークンの oid と一致させる
  issuer:   https://login.microsoftonline.com/{tenantId}/v2.0
  audience: api://AzureADTokenExchange
```

この手動 FIC 登録により、Project MI のトークンを `client_assertion` として Blueprint に提示し、T1（Agent Identity として振る舞うトークン）を取得できるようになった。

### 2.4 検証結果

**試行 1: 既定の FIC のみの状態（手動 FIC 登録前）**

```text
Step 1: Project MI → api://AzureADTokenExchange トークン取得 → ✅ 成功
Step 2: MI トークンを client_assertion として T1 取得 → ❌ 失敗
  error: AADSTS700213: No matching federated identity record found for presented assertion subject
```

**試行 2: Blueprint に Project MI 用の FIC を手動登録した後**

```text
Step 1: Project MI → api://AzureADTokenExchange トークン取得 → ✅ 成功
Step 2: MI トークンを client_assertion として T1 取得 → ✅ 成功
  T1 claims: oid={Blueprint SP OID}, sub=/eid1/c/pub/t/.../AgentIdentityID
```

> **このデモでの対応**: 本デモが目標とする「Hosted Agent 内のコードから Agent Identity として Identity Echo API にアクセスする」シナリオを実現するため、Blueprint に Project MI 用の FIC を手動で登録した。これは Foundry の既定動作の範囲外であり、検証の過程で判明した要件である。

---

## 3. 変更ファイル一覧

| #                    | ファイル                                                      | 変更種別  | 状態 | 内容                                                                        |
| -------------------- | ------------------------------------------------------------- | --------- | ---- | --------------------------------------------------------------------------- |
| **Entra ID 設定**    |                                                               |           |      |                                                                             |
| E1                   | Blueprint FIC                                                 | Graph API | ✅   | Project MI 用の FIC を Blueprint に手動登録                                 |
| E2                   | Agent Identity App Role                                       | Graph API | ✅   | `CallerIdentity.Read.All` Application Permission を付与                     |
| E2-script            | `src/agent/entra-agent-id/grant-approle-to-agent-identity.py` | 新規作成  | ✅   | App Role 付与スクリプト（冪等、`--delete` 対応）                            |
| **Agent Runtime**    |                                                               |           |      |                                                                             |
| A1                   | `src/agent/runtime/auth/token_exchange.py`                    | 新規作成  | ✅   | `get_t1()` + `exchange_app_token(t1)` — T1/TR 取得関数                      |
| A2                   | `src/agent/runtime/tools/autonomous_app.py`                   | 新規作成  | ✅   | `call_resource_api_autonomous_app()` ツール                                 |
| A3                   | `src/agent/runtime/tools/debug.py`                            | 新規作成  | ✅   | `check_agent_environment()` デバッグツール                                  |
| A4                   | `src/agent/runtime/config.py`                                 | 新規作成  | ✅   | `AgentConfig` dataclass（全環境変数定義）                                   |
| A5                   | `src/agent/runtime/main.py`                                   | 新規作成  | ✅   | `ToolDispatchAgent` + `from_agent_framework()` エントリポイント             |
| A6                   | `src/agent/runtime/Dockerfile`                                | 新規作成  | ✅   | `FROM --platform=linux/amd64 python:3.11-slim`、`EXPOSE 8088`               |
| A7                   | `src/agent/runtime/requirements.txt`                          | 新規作成  | ✅   | `azure-ai-agentserver-agentframework==1.0.0b17` 等                          |
| A8                   | `src/agent/agent.yaml`                                        | 新規作成  | ✅   | Foundry Agent 定義（`responses` プロトコル、環境変数）                      |
| **Backend API**      |                                                               |           |      |                                                                             |
| B1                   | `src/backend_api/config.py`                                   | 新規作成  | ✅   | `FOUNDRY_PROJECT_ENDPOINT` + `cognitiveservices→services.ai` ドメイン変換   |
| B2                   | `src/backend_api/foundry_client.py`                           | 新規作成  | ✅   | `invoke_agent()` / `invoke_agent_stream()` — Foundry Agent API クライアント |
| B3                   | `src/backend_api/routes/call_foundry_agent.py`                | 新規作成  | ✅   | `POST /api/demo/autonomous/app` (JSON) + `/stream` (SSE)                    |
| B4                   | `src/backend_api/main.py`                                     | 新規作成  | ✅   | FastAPI app + CORS ミドルウェア                                             |
| B5                   | `src/backend_api/Dockerfile`                                  | 新規作成  | ✅   | `python:3.11-slim` + `uvicorn`、`EXPOSE 8000`                               |
| B6                   | `src/backend_api/requirements.txt`                            | 新規作成  | ✅   | `fastapi`, `azure-ai-projects>=2.0.0`, `azure-identity` 等                  |
| **テストスクリプト** |                                                               |           |      |                                                                             |
| S1                   | `src/agent/scripts/invoke-agent.py`                           | 新規作成  | ✅   | CLI から Hosted Agent を呼び出す E2E テストスクリプト                       |
| **Frontend SPA**     |                                                               |           |      |                                                                             |
| F1                   | `src/frontend/src/api/backendApi.ts`                          | 新規作成  | ✅   | SSE streaming クライアント（Backend API 向け）                              |
| F2                   | `src/frontend/src/components/AutonomousChatPanel.tsx`         | 新規作成  | ✅   | チャット形式 UI（SSE テキストデルタ表示 + ツール出力 JSON 表示）            |
| F3                   | `src/frontend/src/utils/extractAgentToolOutput.ts`            | 新規作成  | ✅   | トークンチェーン結果パース・検証ヘルパー                                    |
| F4                   | `src/frontend/src/App.tsx`                                    | 変更      | ✅   | Autonomous Agent タブ追加                                                   |
| **インフラ**         |                                                               |           |      |                                                                             |
| I1                   | `src/infra/main.acr.tf`                                       | 新規作成  | ✅   | Azure Container Registry                                                    |
| I2                   | `src/infra/main.cognitive.capabilityhost.tf`                  | 新規作成  | ✅   | Capability Host（Hosted Agent 有効化に必須）                                |
| I3                   | `src/infra/main.rbac.services.tf`                             | 変更      | ✅   | ACR RBAC（Project MI → Container Registry Repository Reader）               |
| I4                   | `src/infra/main.containerapp.tf`                              | 新規作成  | ✅   | Container Apps Environment + UAMI                                           |
| I5                   | `src/infra/main.containerapp.apps.tf`                         | 新規作成  | ✅   | Identity Echo API + Backend API の Container App                            |

---

## 4. 各ファイルの具体的な実装内容

### 4.1 Entra ID 設定 (E1, E2)

#### E1: Blueprint FIC — Project MI 用の Federated Identity Credential を手動登録

**なぜ必要か**: §2 で詳述した通り、Foundry が自動プロビジョニングする既定の FIC は Azure ML 内部用であり、Hosted Agent 内のユーザーコードからは利用できない。Project MI のトークンで T1 を取得するには、Blueprint に Project MI の OID を subject とする FIC を手動登録する必要がある。

```text
FIC 登録パラメータ:
  subject:  {Project MI の Object ID}
  issuer:   https://login.microsoftonline.com/{tenantId}/v2.0
  audience: api://AzureADTokenExchange
```

> **注**: FIC の登録は Azure Portal の App Registration > Certificates & secrets > Federated credentials から行うか、Graph API で `POST /applications/{id}/federatedIdentityCredentials` で登録する。

#### E2: Agent Identity への Application Permission 付与

**なぜ必要か**: `client_credentials` で取得した TR の権限は、Agent Identity Service Principal に付与された App Role に依存する。Identity Echo API の `CallerIdentity.Read.All`（Application Permission）を Agent Identity に付与する。

**スクリプト**: `src/agent/entra-agent-id/grant-approle-to-agent-identity.py`

```bash
# App Role 付与
python src/agent/entra-agent-id/grant-approle-to-agent-identity.py

# 取り消し
python src/agent/entra-agent-id/grant-approle-to-agent-identity.py --delete
```

```python
# Graph API v1.0 — App Role Assignment を作成
body = {
    "principalId": agent_identity_sp_id,     # Agent Identity SP OID
    "resourceId": resource_sp_id,            # Identity Echo API SP OID
    "appRoleId": app_role_id,                # CallerIdentity.Read.All の ID
}
resp = requests.post(
    f"{GRAPH_BASE}/servicePrincipals/{resource_sp_id}/appRoleAssignedTo",
    headers=headers, json=body,
)
```

**冪等性**: 既存の App Role Assignment を検索し、存在する場合はスキップ。

---

### 4.2 Agent Runtime — `token_exchange.py` (A1)

共通定数と 2 つの主要関数:

```python
_TOKEN_URL = f"https://login.microsoftonline.com/{config.tenant_id}/oauth2/v2.0/token"
_TOKEN_EXCHANGE_SCOPE = "api://AzureADTokenExchange/.default"
_JWT_BEARER = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
```

#### `get_t1()` — T1（Agent Identity Token）取得

```python
def get_t1() -> dict:
    """Acquire T1 token (Agent Identity token) using Project MI."""
    # Step 1: Get MI token for api://AzureADTokenExchange
    cred = DefaultAzureCredential()
    mi_token = cred.get_token(_TOKEN_EXCHANGE_SCOPE)

    # Step 2: Exchange MI token → T1 (Blueprint token)
    payload = {
        "client_id": config.blueprint_client_id,    # Blueprint の Application ID
        "scope": _TOKEN_EXCHANGE_SCOPE,
        "grant_type": "client_credentials",
        "client_assertion_type": _JWT_BEARER,
        "client_assertion": mi_token.token,          # MSI トークン
        "fmi_path": config.agent_identity_oid,       # Agent Identity の SP OID
    }
    resp = requests.post(_TOKEN_URL, data=payload, timeout=_TIMEOUT)
    # ... success/error handling
```

> **`fmi_path`**: Agent Identity の Service Principal OID を指定。Blueprint がどの Agent Identity として振る舞うかを決定する。

#### `exchange_app_token()` — TR（App-only Resource Token）取得

```python
def exchange_app_token(t1: str) -> dict:
    """Exchange T1 for TR (resource token) using client_credentials."""
    payload = {
        "client_id": config.agent_identity_oid,          # Agent Identity の SP OID
        "scope": config.resource_api_default_scope,      # api://{id}/.default
        "grant_type": "client_credentials",
        "client_assertion_type": _JWT_BEARER,
        "client_assertion": t1,                           # T1 トークン
    }
    resp = requests.post(_TOKEN_URL, data=payload, timeout=_TIMEOUT)
    # ... success/error handling
```

> **返却 TR の claims**: `aud` = Identity Echo API の App ID、`sub`/`oid` = Agent Identity OID、`roles` = `["CallerIdentity.Read.All"]`、`scp` は存在しない（app-only）。

---

### 4.3 Agent Runtime — `tools/autonomous_app.py` (A2)

3 ステップの Token Chain を実行するツール:

```python
"""Autonomous Agent (App) flow tool — T1 → TR (app-only) → Identity Echo API."""

import json
import requests
from agent_framework import tool
from auth.token_exchange import exchange_app_token, get_t1
from config import config


def _run_autonomous_app() -> str:
    result: dict = {
        "name": "call_resource_api_autonomous_app",
        "outputs": {},
        "logs": {
            "step1_get_t1": {},
            "step2_exchange_app_token": {},
            "step3_call_resource_api": {},
        },
    }

    # Step 1: Get T1
    t1_result = get_t1()
    result["logs"]["step1_get_t1"] = {
        "success": t1_result["success"],
        "claims": t1_result.get("claims") if t1_result["success"] else None,
        "error": t1_result.get("error"),
    }
    if not t1_result["success"]:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 2: Exchange T1 → TR (app-only)
    tr_result = exchange_app_token(t1_result["access_token"])
    result["logs"]["step2_exchange_app_token"] = {
        "success": tr_result["success"],
        "claims": tr_result.get("claims") if tr_result["success"] else None,
        "error": tr_result.get("error"),
        "error_description": tr_result.get("error_description"),
    }
    if not tr_result["success"]:
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Step 3: Call Identity Echo API
    api_url = f"{config.resource_api_url}/api/resource"
    resp = requests.get(
        api_url,
        headers={"Authorization": f"Bearer {tr_result['access_token']}"},
        timeout=30,
    )
    result["logs"]["step3_call_resource_api"] = {
        "success": resp.status_code == 200,
        "status_code": resp.status_code,
        "body": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text,
    }

    return json.dumps(result, indent=2, ensure_ascii=False)


@tool(
    name="call_resource_api_autonomous_app",
    description="Call Identity Echo API using the Agent Identity Autonomous Agent (App) flow.",
)
def call_resource_api_autonomous_app() -> str:
    """Call Identity Echo API using the Agent Identity Autonomous App flow.

    Performs the full token chain:
      1. get_t1()           — Project MI → T1 (Agent Identity token)
      2. exchange_app_token(t1) — T1 → TR (app-only resource token)
      3. Call Identity Echo API with TR as Bearer token
    """
    return _run_autonomous_app()
```

**E2E 検証結果（2026-04-04）:**

```json
{
  "step1_get_t1": {
    "success": true,
    "claims": { "oid": "5cbe3864-...", "sub": "/eid1/c/pub/t/.../6fac9afc-..." }
  },
  "step2_exchange_app_token": {
    "success": true,
    "claims": {
      "aud": "52d603ac-...",
      "sub": "6fac9afc-...",
      "roles": ["CallerIdentity.Read.All"]
    }
  },
  "step3_call_resource_api": {
    "success": true,
    "status_code": 200,
    "body": {
      "caller": {
        "tokenKind": "app_only",
        "oid": "6fac9afc-...",
        "roles": ["CallerIdentity.Read.All"]
      }
    }
  }
}
```

---

### 4.4 Agent Runtime — `tools/debug.py` (A3)

環境変数と MSI 認証を確認するデバッグ用ツール。Phase 2 Step A-2 のローカルテストおよびデプロイ検証で使用:

```python
@tool(name="check_agent_environment", description="Check agent runtime environment and credentials.")
def check_agent_environment() -> str:
    """Agent の実行環境を確認する（デバッグ用）"""
    # DefaultAzureCredential で management.azure.com のトークンを取得
    # 環境変数の設定状況を確認
    # T1 トークン取得も試行
```

---

### 4.5 Agent Runtime — `config.py` (A4)

```python
@dataclass(frozen=True)
class AgentConfig:
    """Environment variables for the Foundry Hosted Agent."""
    tenant_id: str = field(default_factory=lambda: _require_env("ENTRA_TENANT_ID"))
    project_endpoint: str = field(default_factory=lambda: _require_env("FOUNDRY_PROJECT_ENDPOINT"))
    model_deployment_name: str = field(default_factory=lambda: _require_env("FOUNDRY_MODEL_DEPLOYMENT_NAME"))
    blueprint_client_id: str = field(default_factory=lambda: _require_env("ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID"))
    agent_identity_oid: str = field(default_factory=lambda: _require_env("ENTRA_AGENT_IDENTITY_CLIENT_ID"))
    resource_api_url: str = field(default_factory=lambda: _require_env("RESOURCE_API_URL"))
    resource_api_client_id: str = field(default_factory=lambda: _require_env("ENTRA_RESOURCE_API_CLIENT_ID"))
    resource_api_scope: str = field(default_factory=lambda: _require_env("ENTRA_RESOURCE_API_SCOPE"))
    resource_api_default_scope: str = field(default_factory=lambda: _require_env("ENTRA_RESOURCE_API_DEFAULT_SCOPE"))

config = AgentConfig()
```

> 全フィールドが `_require_env()` でバリデート — 未設定の場合は起動時に即座にエラー終了。

---

### 4.6 Agent Runtime — `main.py` (A5) — ToolDispatchAgent

```python
class ToolDispatchAgent(Agent):
    """Agent subclass that reads ``force_tool`` from the request metadata
    and forces the model to call exactly that tool.

    Approach: when ``force_tool`` is present, pass ``tools=[forced_tool]``
    to ``super().run()`` so the model only sees a single tool.
    """
    def run(self, messages=None, *, stream=False, session=None, tools=None, options=None, **kwargs):
        force_tool = getattr(self, "_request_headers", {}).get("force_tool")
        if force_tool and force_tool in _TOOL_NAMES:
            self.default_options["tools"] = [_TOOL_BY_NAME[force_tool]]
        else:
            self.default_options["tools"] = list(_TOOL_FUNCS)
        return super().run(messages, stream=stream, session=session, tools=tools, options=options, **kwargs)
```

> **`tool_choice` を不使用の理由**: Agents Threads/Runs バックエンドで `tool_choice` を指定すると hang する（サーバーサイドの問題）。代替として `tools` リストを制限する方式を採用。

---

### 4.7 Agent Runtime — Dockerfile / requirements.txt / agent.yaml (A6-A8)

**Dockerfile:**

```dockerfile
ARG AGENT_PLATFORM=linux/amd64
FROM --platform=$AGENT_PLATFORM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8088
CMD ["python", "main.py"]
```

**requirements.txt:**

```text
azure-ai-agentserver-agentframework==1.0.0b17
azure-identity==1.25.3
httpx==0.28.1
python-dotenv==1.2.2
```

**agent.yaml:**

```yaml
name: demo-entraagtid-agent
definition:
  container_protocol_versions:
    - protocol: responses
      version: v1
  cpu: "1"
  memory: 2Gi
  image: ${FOUNDRY_AGENT_ACR_LOGIN_SERVER}/demo-agent:latest
  environment_variables:
    FOUNDRY_PROJECT_ENDPOINT: ${FOUNDRY_PROJECT_ENDPOINT}
    FOUNDRY_MODEL_DEPLOYMENT_NAME: ${FOUNDRY_MODEL_DEPLOYMENT_NAME}
    RESOURCE_API_URL: ${RESOURCE_API_URL}
    ENTRA_TENANT_ID: ${ENTRA_TENANT_ID}
    ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID: ${ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID}
    ENTRA_AGENT_IDENTITY_CLIENT_ID: ${ENTRA_AGENT_IDENTITY_CLIENT_ID}
    ENTRA_RESOURCE_API_CLIENT_ID: ${ENTRA_RESOURCE_API_CLIENT_ID}
    ENTRA_RESOURCE_API_SCOPE: ${ENTRA_RESOURCE_API_SCOPE}
    ENTRA_RESOURCE_API_DEFAULT_SCOPE: ${ENTRA_RESOURCE_API_DEFAULT_SCOPE}
```

---

### 4.8 Backend API (B1-B6)

#### `config.py` — Foundry エンドポイント変換

```python
def _to_services_endpoint(endpoint: str) -> str:
    """Convert cognitiveservices.azure.com to services.ai.azure.com.
    AIProjectClient must connect via the services.ai.azure.com domain."""
    return re.sub(r"\.cognitiveservices\.azure\.com/", ".services.ai.azure.com/", endpoint)

FOUNDRY_PROJECT_ENDPOINT: str = _to_services_endpoint(os.getenv("FOUNDRY_PROJECT_ENDPOINT", ""))
FOUNDRY_AGENT_NAME: str = "demo-entraagtid-agent"
```

#### `foundry_client.py` — Foundry Agent API クライアント

```python
_project = AIProjectClient(endpoint=FOUNDRY_PROJECT_ENDPOINT, credential=DefaultAzureCredential(), allow_preview=True)
_openai = _project.get_openai_client()

def invoke_agent_stream(message: str, *, force_tool: str | None = None) -> Iterator[str]:
    """Send message to Hosted Agent and yield SSE-formatted lines."""
    agent = _project.agents.get(agent_name=FOUNDRY_AGENT_NAME)
    extra_body = {"agent_reference": {"name": agent.name, "type": "agent_reference"}}
    if force_tool:
        extra_body["metadata"] = {"force_tool": force_tool}

    stream = _openai.responses.create(
        input=[{"role": "user", "content": message}],
        store=False, stream=True, extra_body=extra_body, timeout=180,
    )
    for event in stream:
        data = json.dumps(event.model_dump(), default=str, ensure_ascii=False)
        yield f"event: {event.type}\ndata: {data}\n\n"
```

> **`agent_reference` パターン**: `model` パラメータではなく `extra_body.agent_reference` で Hosted Agent を指定。`endpoint` は `services.ai.azure.com` ドメインを使用。

#### `routes/call_foundry_agent.py` — エンドポイント

```python
class AgentRequest(BaseModel):
    message: str = "Call the resource API using the autonomous app flow."
    force_tool: str | None = None

@router.post("/autonomous/app")         # 一括 JSON レスポンス
@router.post("/autonomous/app/stream")  # SSE ストリーミング
```

#### `main.py` — CORS 設定

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"] + _extra_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

---

### 4.9 テストスクリプト — `invoke-agent.py` (S1)

```python
# src/agent/scripts/invoke-agent.py
# CLI から Hosted Agent を呼び出す E2E テストスクリプト
# - agent.yaml からエージェント名を読み取り
# - AIProjectClient + Responses API で呼び出し
# - --tool オプションで force_tool を指定可能
# - 入力: -j (JSON), -f (ファイル), stdin (-), 位置引数, または scripts/query.json
```

---

### 4.10 Frontend SPA (F1-F4)

#### `backendApi.ts` — SSE streaming クライアント

```typescript
export function runAutonomousAppStream(
  message: string,
  callbacks: StreamCallbacks,
  forceTool?: string,
): AbortController {
  // POST /api/demo/autonomous/app/stream
  // SSE フレームをパース: event: {type}\ndata: {json}\n\n
  // handleSSEEvent で response.output_text.delta / response.output_item.done / response.completed を処理
  // function_call_output → callbacks.onToolOutput (double-encoded JSON 対応)
}
```

#### `AutonomousChatPanel.tsx` — チャット形式 UI

- **SSE テキストデルタ**: `requestAnimationFrame` バッチングで効率レンダリング
- **ツール選択**: Auto / Autonomous App / Autonomous User / Check Environment
- **ツール出力**: 折りたたみ JSON 表示（`<details>` / `<summary>`）
- **自動スクロール**: メッセージ追加時にチャット末尾へ
- **Stop ボタン**: `AbortController` でストリーミング中断

#### `extractAgentToolOutput.ts` — トークンチェーン結果ヘルパー

- `extractCallerInfo(toolOutput)` — Identity Echo API レスポンスの caller 情報を抽出
- `extractTokenChainLogs(toolOutput)` — step1/step2/step3 ログを抽出
- `isTokenChainSuccess(toolOutput)` — 全ステップ成功を判定
- `getCallerType(callerData, loginUpn)` — "Human User" / "Agent User" / "Agent Application" を判定

#### `App.tsx` — タブ UI

```typescript
type ScenarioTab = "autonomous-agent" | "interactive-obo" | "no-agent";
// autonomous-agent: ログイン不要、AutonomousChatPanel を表示
// interactive-obo: ログイン必要、InteractiveOboPanel を表示
// no-agent: ログイン必要、Identity Echo API を直接呼び出し
```

---

## 5. 環境変数

### 5.1 Agent Runtime（`agent.yaml` → コンテナ環境変数）

| 変数名                                     | 値                                           | 用途                                |
| ------------------------------------------ | -------------------------------------------- | ----------------------------------- |
| `FOUNDRY_PROJECT_ENDPOINT`                 | Foundry Project の endpoint URL              | `AzureAIAgentClient` の接続先       |
| `FOUNDRY_MODEL_DEPLOYMENT_NAME`            | LLM デプロイメント名（例: `gpt-5`）          | Agent が使用する LLM モデル         |
| `RESOURCE_API_URL`                         | Identity Echo API の URL                     | API 呼び出し先                      |
| `ENTRA_TENANT_ID`                          | テナント ID                                  | Token endpoint URL 構築             |
| `ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID` | Blueprint の Application (Client) ID         | T1 の `client_id`                   |
| `ENTRA_AGENT_IDENTITY_CLIENT_ID`           | Agent Identity の Service Principal OID      | T1 の `fmi_path`、TR の `client_id` |
| `ENTRA_RESOURCE_API_CLIENT_ID`             | Identity Echo API の Application (Client) ID | トークン検証用                      |
| `ENTRA_RESOURCE_API_SCOPE`                 | `api://{id}/CallerIdentity.Read`             | delegated フロー用 scope            |
| `ENTRA_RESOURCE_API_DEFAULT_SCOPE`         | `api://{id}/.default`                        | app-only フロー用 scope             |

### 5.2 Backend API（Container App 環境変数）

| 変数名                     | 値                               | 用途                       |
| -------------------------- | -------------------------------- | -------------------------- |
| `ENTRA_TENANT_ID`          | テナント ID                      | (未使用だが将来の拡張用)   |
| `FOUNDRY_PROJECT_ENDPOINT` | Foundry Project の endpoint URL  | `AIProjectClient` の接続先 |
| `FRONTEND_SPA_APP_URL`     | SPA のデプロイ URL（オプション） | CORS 許可オリジンに追加    |

---

## 6. 段階的検証チェックリスト（実施済み）

> 以下は Phase 2・Phase 3 の実装中に段階的に検証した結果の記録である。
> 「各フェーズで 1 つの新しい概念だけを追加する」原則を Phase 内のサブステップにも適用し、問題発生時の切り分けを容易にした。

### Phase 2: Foundry Hosted Agent 最小実装（Autonomous Agent App Flow）

#### 目的

Foundry Hosted Agent のコンテナ内で **T1 取得 → TR 取得（client_credentials）→ Identity Echo API 呼び出し** を動作させる。

Entra Agent ID の設定（Blueprint / Agent Identity / Federated Credential）が正しいことを確立する最初のフェーズ。**SPA との統合はこのフェーズでは行わない**。

#### 実装チェックリストの設計方針

> Phase 2 は Foundry Hosted Agent という**実績のない構成要素**を初めて導入するフェーズである。基本方針「各フェーズで 1 つの新しい概念だけを追加する」を Phase 内のサブステップにも徹底するため、以下の 5 ステップ構成で段階的に検証する。
>
> | #       | サブステップ                       | 新たに検証する概念                               | 失敗時の切り分け                            |
> | ------- | ---------------------------------- | ------------------------------------------------ | ------------------------------------------- |
> | **A-1** | インフラプロビジョニング           | ACR, Capability Host, RBAC                       | Terraform / ARM API                         |
> | **A-2** | Agent コード + ローカルテスト      | Agent Framework, hosting adapter, `@ai_function` | コード / SDK / フレームワーク               |
> | **A-3** | Foundry デプロイ + MSI 確認        | Docker build, ACR push, Foundry ランタイム, MSI  | ACR pull / Foundry ランタイム / MSI         |
> | **A-4** | Identity Echo API クラウドデプロイ | Container Apps Environment, Dockerfile, Ingress  | Terraform / ACR push / Container Apps       |
> | **B**   | Resource API 統合                  | T1/TR Token Exchange, Entra Agent ID             | Blueprint / Agent Identity / App Permission |
> | **C**   | Backend API 統合 + curl テスト     | Foundry SDK 呼び出し, E2E パス                   | Backend API の MSI / SDK バージョン         |
>
> 各ステップで「直前まで動いていた」ことが確定しているため、問題が発生してもどの層の障害かを即座に特定できる。

#### 実装チェックリスト

##### Step A-1: インフラプロビジョニング（Terraform IaC）

> **製品名の補正**: 本ドキュメントの以前の版では「Foundry Studio」と記載していたが、この名前の製品は存在しない。正しくは以下の通り:
>
> - **Microsoft Foundry**: 製品全体の名称（旧称: Azure AI Foundry）
> - **Microsoft Foundry portal** (`ai.azure.com`): Web UI（旧 Azure AI Studio）
> - **Agent Builder**: Foundry portal 内のエージェント作成・管理 UI
> - **Foundry Agent Service**: Hosted Agent を含むエージェントランタイムサービス
>
> また、Hosted Agent の作成は Portal の UI ではなく、以下のコードベースの方法で行う:
>
> - **Foundry SDK** (`azure-ai-projects >= 2.0.0`): `client.agents.create_version()` で IaC/スクリプトベースの作成
> - **Azure Developer CLI**: `azd ai agent init` + `azd up` によるデプロイ
> - **VS Code Foundry extension**: VS Code 上のエージェント開発ワークフロー
>
> 参照: [What are hosted agents?](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)

**目的**: Hosted Agent の実行に必要な Azure リソースをプロビジョニングする。コードは一切書かない。

**Terraform IaC（`src/infra/`）で作成・管理するリソース:**

- [x] Foundry Project を作成 — ✅ `azurerm_cognitive_account_project.this`（Phase 1 で作成済み）
- [x] Azure Container Registry (ACR) を作成 — ✅ `main.acr.tf`（`crfounddevb9943130a9c4c7.azurecr.io`）
- [x] Capability Host を作成 — ✅ `main.cognitive.capabilityhost.tf`（API `2025-10-01-preview` — `enablePublicHostingEnvironment` はこのバージョン以降で対応。azapi が `2025-12-01` GA に対応次第更新）
- [x] ACR RBAC を設定 — ✅ `main.rbac.services.tf`（`Container Registry Repository Reader` → Project MI `89ccb38c-...`）

**確認方法:**

- [x] `terraform apply` が成功する — ✅ 実行済み
- [x] ACR リソースの存在を確認 — ✅ `az acr show -n crfounddevb9943130a9c4c7`（SKU: Basic, Login Server: `crfounddevb9943130a9c4c7.azurecr.io`）
- [x] Capability Host の存在を確認 — ✅ `az rest --method GET --url .../capabilityHosts/accountcaphost`（`provisioningState: Succeeded`, `capabilityHostKind: Agents`, `enablePublicHostingEnvironment: true`）

**切り分けポイント:**

| 問題                           | 原因の候補                                                    |
| ------------------------------ | ------------------------------------------------------------- |
| Capability Host 作成が失敗する | API バージョン誤り、リージョン非対応、`capabilityHostKind` 値 |
| ACR RBAC 付与が失敗する        | ロール名の誤り、Project MI の principal_id 取得タイミング     |

---

##### Step A-2: Agent コード作成 + ローカルテスト

**目的**: 最小の Agent コードを作成し、**ローカル環境で** hosting adapter (`localhost:8088`) が正しく動作することを確認する。この段階では Foundry へのデプロイも MSI も使用しない。

> **ローカルテストが鍵**: hosting adapter は `localhost:8088` でローカルサーバーを起動するため、Foundry にデプロイしなくてもコードの正しさを検証できる。ローカルで動くのに Foundry で動かなければ、問題は 100% インフラ側であると確定できる。
>
> ローカル環境では `DefaultAzureCredential` が Azure CLI クレデンシャルにフォールバックするため、MSI 固有の検証は Step A-3 で行う。

**最小動作確認用の `@ai_function`:**

この段階では Resource API（Identity Echo API）は呼び出さない。代わりに、環境変数と認証情報を確認するデバッグ用ツールを実装する:

```python
@ai_function
def check_agent_environment() -> str:
    """Agent の実行環境を確認する（デバッグ用）"""
    from azure.identity import DefaultAzureCredential
    cred = DefaultAzureCredential()
    token = cred.get_token("https://management.azure.com/.default")
    return json.dumps({
        "status": "ok",
        "credential_obtained": bool(token.token),
        "token_expires_on": token.expires_on,
        "env_project_endpoint": os.getenv("FOUNDRY_PROJECT_ENDPOINT", "NOT SET"),
        "env_blueprint_client_id": os.getenv("ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID", "NOT SET"),
        "env_agent_identity_oid": os.getenv("ENTRA_AGENT_IDENTITY_CLIENT_ID", "NOT SET"),
    }, indent=2)
```

**コーディング（`src/agent/runtime/`）:**

- [x] `src/agent/runtime/main.py` — ✅ `Agent` + `from_agent_framework(agent).run()` エントリポイント。SDK `azure-ai-agentserver-agentframework 1.0.0b17` で `Agent`（旧称 `ChatAgent`）、`tool`（旧称 `@ai_function`）に更新
- [x] `src/agent/runtime/tools/debug.py` — ✅ `check_agent_environment()` + `try_t1_token_acquisition()` Function Tool（`@tool` デコレータ）
- [x] `src/agent/runtime/config.py` — ✅ `AgentConfig` dataclass（全環境変数定義済み）
- [x] `src/agent/requirements.txt` — ✅ `azure-ai-agentserver-agentframework`, `azure-identity`, `httpx`, `python-dotenv`
- [x] `src/agent/runtime/Dockerfile` — ✅ `FROM --platform=linux/amd64 python:3.11-slim`、`EXPOSE 8088`
- [x] `src/agent/agent.yaml` — ✅ azd デプロイ用定義ファイル
- [x] `src/agent/runtime/requirements.txt` — ✅ `azure-ai-agentserver-agentframework`, `azure-identity`, `httpx`, `python-dotenv`

> **SDK 名称変更メモ**: 計画書作成時の仮称と実際の SDK (v1.0.0b17) の対応:
>
> - `ChatAgent` → `Agent` (`from agent_framework import Agent`)
> - `@ai_function` → `@tool` (`from agent_framework import tool`)
> - `AzureAIAgentClient` は `from agent_framework_azure_ai import AzureAIAgentClient`
> - `from_agent_framework` は `from azure.ai.agentserver.agentframework import from_agent_framework`

**ローカルテスト:**

- [x] `python main.py` でローカルサーバーが `localhost:8088` で起動する — ✅ `FoundryCBAgent server started successfully on port 8088`
- [x] `POST http://localhost:8088/responses` に `{"input": "環境を確認して"}` を送信し、`check_agent_environment` の結果が返る — ✅ ツール呼び出し成功、LLM が日本語で結果を要約
- [x] レスポンスに `credential_obtained: true` が含まれる（ローカルでは Azure CLI 認証） — ✅ 確認済み

**切り分けポイント:**

| 問題                                      | 原因の候補                                                                              |
| ----------------------------------------- | --------------------------------------------------------------------------------------- |
| `from_agent_framework` でインポートエラー | `azure-ai-agentserver-agentframework` 未インストール / バージョン不一致                 |
| サーバーが起動しない                      | `FOUNDRY_PROJECT_ENDPOINT` 未設定、`FOUNDRY_MODEL_DEPLOYMENT_NAME` が存在しないモデル名 |
| `@ai_function` が LLM に呼ばれない        | 関数の docstring 不足、LLM のモデルデプロイ問題                                         |

---

##### Step A-3: Foundry デプロイ + MSI 動作確認

**目的**: Step A-2 で動作確認済みのコードを Foundry Agent Service にデプロイし、**コンテナが起動すること**と **MSI トークンが取得できること**を確認する。

> **注**: Hosted Agent version の作成は ARM リソースではなく Foundry Data Plane API 経由のため、Terraform では管理できない。Python スクリプト（`src/scripts/`）または `azd ai agent` CLI で自動化する。

**デプロイ操作:**

- [x] Docker イメージをビルド（`docker build --platform linux/amd64`）→ ACR に push（`az acr login` + `docker push`） — ✅ v1〜v8 まで繰り返しビルド・push 済み
- [x] Foundry SDK で Hosted Agent version を作成（`client.agents.create_version()` with `HostedAgentDefinition`） — ✅ `HostedAgentDefinition` + `HeadersPolicy(Foundry-Features: HostedAgents=V1Preview)` で作成
- [x] Agent deployment を開始（`az cognitiveservices agent start` or SDK） — ✅ v3 以降 Healthy 状態を確認

**Agent Identity の確認:**

> **重要**: Hosted Agent の Agent Identity ライフサイクルには 2 段階がある:
>
> 1. **未 Publish**: Foundry Project 共有の Agent Identity Blueprint + Agent Identity が自動プロビジョニングされる（プロジェクト内の全エージェントで共有）。Azure Portal > Foundry Project > JSON View から `agentIdentityId` と `agentIdentityBlueprintId` を確認可能。
> 2. **Publish 後**: Agent Application リソースが作成され、エージェント固有の Agent Identity Blueprint + Agent Identity が新たにプロビジョニングされる。**RBAC 権限は自動移行されないため、再設定が必要**。
>
> Phase 2 ではまず未 Publish 状態でテストし、Phase 3 以降で Publish を検討する。
>
> 参照: [Agent identity concepts in Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-identity)

- [x] Foundry Project の JSON View（Azure Portal）から共有 Agent Identity の `agentIdentityId` を確認 — ✅ `agentIdentityId` と `agentIdentityBlueprintId` の両方がプロビジョニング済みであることを確認

**動作確認:**

- [x] Foundry Agent API 経由（SDK or curl）で Agent に「環境を確認して」と送信 — ✅ `openai.responses.create()` + `agent_reference` で呼び出し成功
- [x] `check_agent_environment` の結果が返り、`credential_obtained: true`（MSI 経由）を確認 — ✅ JWT decode で `appid=4577bb8c`（Project MI）を確認
- [x] 環境変数（`FOUNDRY_PROJECT_ENDPOINT`, `ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID` 等）が正しく設定されていることを確認 — ✅ 全環境変数がコンテナ内で参照可能

**切り分けポイント:**

| 問題                                          | 原因の候補                                                  |
| --------------------------------------------- | ----------------------------------------------------------- |
| Agent version 作成が失敗する                  | ACR イメージ名/タグ誤り、Capability Host 未作成             |
| コンテナが起動しない（`Failed`）              | `--platform linux/amd64` 未指定、ポート 8088 未 EXPOSE      |
| ACR pull が失敗する（`AcrPullWithMSIFailed`） | Project MI に `Container Registry Repository Reader` 未付与 |
| MSI トークン取得が失敗する                    | `DefaultAzureCredential` のスコープ誤り、MI 未有効化        |
| 環境変数が `NOT SET` になる                   | `create_version` の `environment_variables` 設定漏れ        |

##### Step A-3 実証結果: Hosted Agent ランタイム環境と T1 取得検証

> **検証日**: 2026-03-31
> **検証バージョン**: v8 (最終確認)、v3〜v8 で段階的に検証
>
> FIC メカニズムの詳細な解説は §2 を参照。ここでは検証ログのみ記載する。

**ランタイム環境の実態（v5 環境変数ダンプより）:**

Hosted Agent のコンテナは **Azure Container Apps** 上で動作する。ランタイムが注入する主要な環境変数:

| 環境変数            | 値                          | 説明                                                                                                                    |
| ------------------- | --------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `AZURE_CLIENT_ID`   | (自動注入)                  | Foundry Project の System-Assigned MI の Client ID。`DefaultAzureCredential()` がこの値を検出して MI トークンを取得する |
| `IDENTITY_ENDPOINT` | Container Apps MI endpoint  | Managed Identity トークン取得エンドポイント                                                                             |
| `MSI_ENDPOINT`      | Container Apps MSI endpoint | 同上（レガシー形式）                                                                                                    |

**T1 トークン取得の実証:**

**試行 1: 既定の FIC のみの状態（手動 FIC 登録前）** → ❌ `AADSTS700213: No matching federated identity record`（→ §2.2 で詳述）

**試行 2: Blueprint に Project MI 用の FIC を手動登録した後（v8 での最終結果）**

```text
Step 1: Project MI → api://AzureADTokenExchange トークン取得 → ✅ 成功
Step 2: MI トークンを client_assertion として Blueprint の T1 取得 → ✅ 成功 (HTTP 200)
  T1 claims:
    aud: {api://AzureADTokenExchange の Resource ID}
    iss: https://login.microsoftonline.com/{tenantId}/v2.0
    sub: /eid1/c/pub/t/{tenantId_b64}/a/{appId_b64}/{Agent Identity ID}
    oid: {Blueprint の Service Principal Object ID}
    idtyp: app
```

**Agent 呼び出し方法の確定（→ §4.8 に詳細）:**

Hosted Agent の呼び出しは Responses API + `extra_body.agent_reference` で行う。`model` パラメータではなく `agent_reference` で Hosted Agent を指定し、`endpoint` は `services.ai.azure.com` ドメインを使用する。

---

##### Step A-4: Identity Echo API クラウドデプロイ

**目的**: Step B で Hosted Agent から Identity Echo API を呼び出すには、Identity Echo API がクラウド上でアクセス可能である必要がある。Phase 1 ではローカル環境で動作確認したが、Hosted Agent はクラウド上のコンテナで実行されるため `localhost` には到達できない。**Step B の前提条件として、Identity Echo API を Azure Container Apps にデプロイする。**

> **計画書 §4.1 との整合**: Identity Echo API のデプロイ先は §4.1 で Azure Container Apps（Consumption）と既に決定済み。Phase 3 の E2E 統合以降もそのまま使い続けるため、使い捨てのリソースにはならない（基本方針に合致）。

**なぜこのタイミングか:**

元の計画書では Identity Echo API のクラウドデプロイを Phase 1 / Phase 3 のデプロイタスクに含めていたが、Phase 2 Step B のテストに必要であることが判明した。Step A-1 のインフラ拡張として位置づけ、Agent コード側の変更は不要（`RESOURCE_API_URL` 環境変数をクラウド URL に差し替えるのみ）。

**Terraform IaC（`src/infra/`）で作成するリソース:**

- [x] Container Apps Environment を作成 — ✅ `main.containerapp.tf`（`azurerm_container_app_environment.this` + `azurerm_user_assigned_identity.container_apps`）
- [x] Identity Echo API の Container App を作成 — ✅ `main.containerapp.apps.tf`（`azurerm_container_app.apps["identity-echo-api"]`、External Ingress、`targetPort: 8000`、FQDN: `ca-identity-echo-api-86d21f.gentlesand-f7ed7d5b.swedencentral.azurecontainerapps.io`）

**コーディング:**

- [x] `src/identity_echo_api/Dockerfile` を作成 — ✅ `python:3.11-slim` + `uvicorn`、`EXPOSE 8000`
- [x] Identity Echo API イメージを既存 ACR に push — ✅ `null_resource.acr_build["identity-echo-api"]` で `az acr build` 自動実行

**環境変数設定（Container App）:**

- [x] `ENTRA_TENANT_ID` — ✅ `local.container_app_computed_env` で Terraform data source から自動注入
- [x] `ENTRA_RESOURCE_API_CLIENT_ID` — ✅ `local.container_app_computed_env` で `azuread_application.resource_api.client_id` から自動注入

**確認方法（3 段階で検証）:**

> **検証原則**: 「Phase 1 で動作実績のある SPA」をまず使い、クラウド上の Identity Echo API 自体の正常動作を確立してから、Hosted Agent のテストに進む。これにより、Step B で問題が発生した場合に「Identity Echo API の問題」と「Token Exchange の問題」を即座に切り分けられる。

**段階 1: インフラ疎通確認**

- [x] `terraform apply` が成功する — ✅ `azurerm_container_app.apps["identity-echo-api"]` 作成済み
- [x] `curl https://{fqdn}/health` → `{"status": "ok"}` — ✅ HTTP 200 + `{"status":"ok"}` 確認済み
- [x] `curl https://{fqdn}/api/resource` → HTTP 401（Bearer トークンなし） — ✅ HTTP 401 + `{"detail":"Missing or invalid Authorization header"}` 確認済み

**段階 2: SPA（Phase 1）からのクラウド API 動作確認**

- [x] SPA の `RESOURCE_API_URL` をクラウド URL（`https://{fqdn}`）に変更 — ✅ `src/.env` に `RESOURCE_API_URL=https://ca-identity-echo-api-86d21f.gentlesand-f7ed7d5b.swedencentral.azurecontainerapps.io` 設定済み
- [x] Identity Echo API の CORS `allow_origins` にクラウド SPA のオリジン（またはローカル `localhost:5173`）を含めることを確認 — ✅ `allow_origins` に `http://localhost:5173` 含む
- [x] SPA でログイン → Identity Echo API 呼び出し → `tokenKind: "delegated"` が返ることを確認 — ✅ 確認済み
  - Phase 1 のローカル環境で確認済みのフローをクラウド API に向けて再実行するだけなので、ここで失敗すれば問題は 100% デプロイ側（CORS / Ingress / 環境変数）にある

> **この段階が通れば**: Identity Echo API がクラウド上で正しくトークン検証・レスポンス返却できることが確定する。

**段階 3: Hosted Agent への反映**

- [x] Hosted Agent の環境変数 `RESOURCE_API_URL` を Container App の FQDN（`https://{app-name}.{region}.azurecontainerapps.io`）に更新し、Agent version を再作成 — ✅ デプロイ確認済み

**切り分けポイント:**

| 問題                                               | 原因の候補                                                                |
| -------------------------------------------------- | ------------------------------------------------------------------------- |
| Container App が起動しない                         | Dockerfile の CMD 誤り、ポート不一致（`targetPort` ≠ `EXPOSE`）           |
| ACR pull が失敗する                                | Container App MI に ACR `AcrPull` ロール未付与、または ACR admin 認証漏れ |
| `/health` が応答しない                             | Ingress 設定（External / Internal）、Container App のプロビジョニング中   |
| SPA からクラウド API が CORS エラー                | Identity Echo API の `allow_origins` にオリジン未追加                     |
| SPA からクラウド API でトークンが拒否される        | 環境変数（`ENTRA_TENANT_ID` / `ENTRA_RESOURCE_API_CLIENT_ID`）の設定誤り  |
| Hosted Agent から Identity Echo API に到達できない | `RESOURCE_API_URL` の設定誤り、DNS 解決失敗                               |

---

##### Step B: Resource API 統合（Token Exchange + Identity Echo API 呼び出し）

**目的**: Step A-4 で「Identity Echo API がクラウド上でアクセス可能」な状態、Step A-3 で「MSI が動く Hosted Agent」が確立した状態から、T1/TR Token Exchange を実装し、Identity Echo API を呼び出す。この段階で Backend API はまだ使わず、Agent の Function Tool から直接 Resource API を呼ぶ。

**前提条件（Step A-4 で確立済み）:**

- Identity Echo API がクラウド上で HTTPS アクセス可能
- `curl https://{fqdn}/health` → `{"status": "ok"}` で疎通確認済み
- **SPA（Phase 1）からクラウド API を呼び出し、`tokenKind: "delegated"` が返ることを確認済み**（Identity Echo API のトークン検証が正常に動作する証拠）
- Hosted Agent の `RESOURCE_API_URL` 環境変数がクラウド URL を指している

**コーディング（`src/agent/runtime/` に追加）:**

- [x] `src/agent/runtime/auth/token_exchange.py` — T1・TR 取得ロジック — ✅ 実装済み
  - `get_t1()` — `DefaultAzureCredential().get_token()` で MSI トークンを取得し、`client_credentials` + `fmi_path` で T1 を取得
  - `exchange_app_token(t1)` — T1 → TR（`client_credentials`、app-only、scope = `RESOURCE_API_DEFAULT_SCOPE`）
- [x] `src/agent/runtime/tools/autonomous_app.py` — `call_resource_api_autonomous_app()` Function Tool（`@tool` デコレータ） — ✅ 実装済み
  - `get_t1()` → `exchange_app_token()` → `GET /api/resource`（Bearer TR）→ レスポンス JSON を返す
- [x] `src/agent/runtime/main.py` — ツールリストに `call_resource_api_autonomous_app` を追加（`check_agent_environment` も残す） — ✅ 実装済み

**権限設定:**

- [x] Agent Identity に `CallerIdentity.Read.All`（Application Permission）を付与 — ✅ `src/agent/entra-agent-id/grant-approle-to-agent-identity.py` スクリプトで Graph API 経由で付与済み
  - Graph API `POST /servicePrincipals/{resourceId}/appRoleAssignedTo` で App Role Assignment を作成
  - 冪等（既存の場合はスキップ）、`revoke` サブコマンドで取り消し可能

**動作確認:**

- [x] Docker イメージを再ビルド → ACR push → Agent version 更新 — ✅ デプロイ済み
- [x] Foundry Agent API 経由で Agent に「リソース API を autonomous app フローで呼び出して」と送信 — ✅ `scripts/invoke-agent.py` で確認
- [x] Identity Echo API から `tokenKind: "app_only"` と Agent Identity の OID が返ることを確認 — ✅ 全 3 ステップ成功を確認

**検証結果（2026-04-04）:**

```json
{
  "step1_get_t1": {
    "success": true,
    "claims": { "oid": "5cbe3864-...", "sub": "/eid1/c/pub/t/.../6fac9afc-..." }
  },
  "step2_exchange_app_token": {
    "success": true,
    "claims": {
      "aud": "52d603ac-...",
      "sub": "6fac9afc-...",
      "roles": ["CallerIdentity.Read.All"]
    }
  },
  "step3_call_resource_api": {
    "success": true,
    "status_code": 200,
    "body": {
      "caller": {
        "tokenKind": "app_only",
        "oid": "6fac9afc-...",
        "roles": ["CallerIdentity.Read.All"]
      }
    }
  }
}
```

> **確認事項**: TR の `aud` が Identity Echo API の App ID（`52d603ac-...`）と一致、`sub`/`oid` が Agent Identity OID（`6fac9afc-...`）と一致、`roles` に `CallerIdentity.Read.All` が含まれる。Identity Echo API は `tokenKind: "app_only"` を正しく判定。

**切り分けポイント:**

| 問題                                   | 原因の候補                                                                      |
| -------------------------------------- | ------------------------------------------------------------------------------- |
| T1 取得が失敗する                      | Federated Credential の設定誤り、MSI の権限不足、Blueprint Client ID 誤り       |
| TR 取得が失敗する                      | Agent Identity の Application Permission 未付与、scope 形式（`/.default` 必須） |
| Identity Echo API がトークンを拒否する | `aud` の不一致（Identity Echo API の App ID と不一致）                          |
| `tokenKind` が `app_only` にならない   | TR 取得フローが `client_credentials` になっていない                             |

---

##### Step C: Backend API 統合 + curl / REST テスト

**目的**: Step B で「Hosted Agent が Identity Echo API を正しく呼べる」ことが確立した状態から、Backend API を追加し、外部クライアントから呼び出し可能な API エンドポイントとして公開する。

**コーディング（`src/backend_api/`）:**

- [x] `src/backend_api/config.py` — 環境変数（`FOUNDRY_PROJECT_ENDPOINT`、`ENTRA_TENANT_ID`）+ `cognitiveservices.azure.com` → `services.ai.azure.com` ドメイン変換 — ✅ 実装済み
- [x] `src/backend_api/foundry_client.py` — Foundry Agent API 呼び出しクライアント（`AIProjectClient` + `DefaultAzureCredential()` で MSI 認証） — ✅ 実装済み
  - `invoke_agent(message)` — 一括レスポンス版（`openai.responses.create()` → パース → dict 返却）
  - `invoke_agent_stream(message)` — SSE ストリーミング版（`stream=True` → OpenAI イベントを SSE フレームとして yield）
- [x] `src/backend_api/routes/demo.py` — ✅ 実装済み
  - `POST /api/demo/autonomous/app` — 一括 JSON レスポンス
  - `POST /api/demo/autonomous/app/stream` — SSE ストリーミング（`text/event-stream`）
- [x] `src/backend_api/main.py` — FastAPI アプリ（CORS は Phase 3 まで不要） — ✅ 実装済み
- [x] `src/backend_api/requirements.txt` — `fastapi`, `uvicorn`, `azure-ai-projects>=2.0.0`, `azure-identity>=1.19.0`, `python-dotenv` — ✅ 作成済み
- [x] `src/backend_api/Dockerfile` — `python:3.11-slim` + `uvicorn`、`EXPOSE 8000` — ✅ 作成済み

**SSE ストリーミング対応（確認済み）:**

> Hosted Agent は OpenAI Responses API の `stream=True` に対応しており、標準的なストリーミングイベント（`response.created`, `response.output_text.delta`, `response.function_call_arguments.done`, `response.completed` 等）を返す。Backend API はこれらのイベントを `event: {type}\ndata: {json}\n\n` の SSE フレームとしてそのまま中継する。フロントエンドでは標準的な `EventSource` や OpenAI SDK 互換パーサーで消費可能。

**エンドポイント設計:**

| パス                                   | 方式                 | リクエストボディ     | 用途                       |
| -------------------------------------- | -------------------- | -------------------- | -------------------------- |
| `POST /api/demo/autonomous/app`        | 一括 JSON レスポンス | `{"message": "..."}` | curl / REST テスト         |
| `POST /api/demo/autonomous/app/stream` | SSE ストリーミング   | `{"message": "..."}` | SPA からのリアルタイム表示 |

**権限設定:**

- [x] Backend API の専用 UAMI（`uami-ca-foundry-*`）に `Cognitive Services User` ロールを付与（Foundry Account スコープで） — ✅ Terraform IaC 定義・apply 済み

**動作確認（ローカル）:**

- [x] `GET /health` → `{"status": "ok"}` — ✅ 確認済み
- [x] `POST /api/demo/autonomous/app` に curl → `tokenKind: "app_only"` と Agent Identity OID が返ることを確認 — ✅ E2E 成功（`oid: 6fac9afc-...`, `roles: ["CallerIdentity.Read.All"]`）
- [x] `POST /api/demo/autonomous/app/stream` に curl → SSE イベントがストリーミングで返ることを確認 — ✅ `response.created` → `response.output_text.delta` (逐次) → `response.completed` の一連の SSE イベントを確認

**切り分けポイント:**

| 問題                                                    | 原因の候補                                                                 |
| ------------------------------------------------------- | -------------------------------------------------------------------------- |
| Backend API から Foundry Agent API の呼び出しが失敗する | Backend API の MSI に `Cognitive Services User` ロール未付与               |
| Foundry SDK のバージョンエラー                          | `azure-ai-projects >= 2.0.0` 未インストール                                |
| レスポンスがタイムアウトする                            | Agent deployment が停止状態、min_replicas = 0 でコールドスタート           |
| SSE イベントがバッファリングされて一括で返る            | リバースプロキシのバッファリング設定（`X-Accel-Buffering: no` で対応済み） |

---

### Phase 3: SPA + Autonomous Agent App Flow 統合（E2E）

#### 目的

Phase 1 の SPA と Phase 2 の Backend API + Foundry Hosted Agent を接続し、**Autonomous Agent App Flow のエンドツーエンドを完成させる**。

#### 追加・変更するコンポーネント

| コンポーネント   | 変更内容                                | 実装結果 |
| ---------------- | --------------------------------------- | -------- |
| **Frontend SPA** | Autonomous チャット UI と結果表示を追加 | ✅ 完了  |
| **Backend API**  | CORS 設定、エラーハンドリングを追加     | ✅ 完了  |

#### 実装内容

**Frontend SPA 変更点（実装済み）**

- タブベースの UI（`autonomous-app` / `identity-echo-debug`）を追加。Autonomous Agent App タブはログイン不要
- チャット形式の `AutonomousChatPanel` でユーザーが自由なメッセージを送信可能
- `POST /api/demo/autonomous/app/stream` を SSE で呼び出し、テキストデルタをリアルタイム表示
- ツール出力（トークンチェーン結果）を折りたたみ JSON で表示、成功/失敗バッジ付き

**Backend API 変更点（実装済み）**

- CORS 設定（`http://localhost:5173`, `http://localhost:4173` を許可）
- `routes/call_foundry_agent.py` で Foundry Agent API 呼び出し失敗時に HTTP 502 エラーを返却

#### 完成する E2E フロー

```text
👤 ユーザー（ログイン不要）
  → [チャット送信] → SPA (AutonomousChatPanel)
  → POST /api/demo/autonomous/app/stream → Backend API (MSI token, SSE)
  → Foundry Hosted Agent
      → T1 取得 (Project MSI) → TR 取得 (client_credentials)
      → GET /api/resource (Bearer TR) → Identity Echo API
  ← SSE: response.created → function_call → function_call_output
     → output_text.delta (逐次) → response.completed
  ← SPA: テキストデルタをリアルタイム表示 + ツール出力を JSON で表示
```

> 詳細なシーケンスは設計書 §5.2 を参照。

#### 実装チェックリスト

**(1) Backend API の変更（`src/backend_api/`）**

- [x] `src/backend_api/main.py` に CORS ミドルウェアを追加（許可オリジン: `http://localhost:5173`, `http://localhost:4173`） — ✅ `CORSMiddleware` で `allow_methods=["GET", "POST"]`, `allow_headers=["*"]` を設定
- [x] エラーハンドリング（Foundry Agent API 呼び出し失敗時の 502 エラー整形） — ✅ `routes/call_foundry_agent.py` で `try/except` → `HTTPException(status_code=502, detail="Hosted Agent invocation failed")`

**(2) Frontend SPA の変更（`src/frontend/`）**

- [x] `src/frontend/src/api/backendApi.ts` を新規作成し `runAutonomousAppStream()` 関数を追加（`POST /api/demo/autonomous/app/stream` を SSE で呼び出す、認証トークン不要） — ✅ SSE フレームパース（`response.output_text.delta`, `response.function_call_output`, `response.completed` 等）、`AbortController` によるキャンセル対応
- [x] `src/frontend/src/components/AutonomousChatPanel.tsx` を新規作成（チャット形式 UI） — ✅ デフォルトメッセージ「Call the resource API using the autonomous app flow.」、SSE テキストデルタの `requestAnimationFrame` 効率レンダリング、ツール出力の折りたたみ JSON 表示、自動スクロール、Stop ボタン
- [x] `src/frontend/src/utils/extractAgentToolOutput.ts` を新規作成（トークンチェーン検証ヘルパー） — ✅ `extractCallerInfo()`, `isTokenChainData()`, `isTokenChainSuccess()` の 3 関数
- [x] `src/frontend/src/App.tsx` にタブ UI を組み込み — ✅ `autonomous-app` タブ（ログイン不要）と `identity-echo-debug` タブ（ログイン必要）の 2 タブ構成。`AutonomousChatPanel` から `onToolOutput` / `onStreamComplete` コールバックでトークンチェーン結果を受け取り、成功/失敗バッジを表示

> **計画との差分**: 当初計画では `demoApi.ts` + `ScenarioPanel.tsx`（シナリオ選択 UI）を想定していたが、実装では `backendApi.ts` + `AutonomousChatPanel.tsx`（チャット形式 UI）を採用した。チャット形式にすることで、LLM のストリーミングレスポンスをリアルタイム表示でき、ユーザーが自然言語でクエリを送信できる柔軟な UI となった。`CallerInfo.tsx` は変更不要で、`extractAgentToolOutput.ts` のヘルパーがツール出力から caller 情報を抽出する役割を担う。

**(3) E2E 動作確認（ローカル）**

- [x] SPA のチャット UI → Backend API → Foundry Agent → Identity Echo API の E2E が通ることを確認 — ✅ `http://localhost:5173` からの SSE ストリーミング表示を確認
- [x] 画面に `tokenKind: "app_only"`、Agent Identity OID が表示されることを確認 — ✅ ツール出力の `step3_call_resource_api.body.caller` に `tokenKind: "app_only"`, `oid: "6fac9afc-..."`, `roles: ["CallerIdentity.Read.All"]` が表示。トークンチェーン成功バッジ（「取得済み」）も表示

> **E2E フローの詳細**: §1.3 の「Phase 3（SPA 統合 E2E）」図を参照。

#### 切り分けポイント

| 問題                                            | 原因の候補                                                              |
| ----------------------------------------------- | ----------------------------------------------------------------------- |
| フロントエンドから Backend API がブロックされる | CORS 設定漏れ                                                           |
| Backend API の MSI が Foundry を呼び出せない    | Backend API の Managed Identity に Cognitive Services User ロール未付与 |

---
