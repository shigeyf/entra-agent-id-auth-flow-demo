# 実装タスク計画書

| 項目               | 内容                                       |
| ------------------ | ------------------------------------------ |
| **ドキュメント名** | Entra Agent ID デモアプリ 実装タスク計画書 |
| **バージョン**     | 1.0                                        |
| **作成日**         | 2026-03-27                                 |
| **ステータス**     | ドラフト                                   |

---

## 1. 方針

### 1.1 基本方針

このデモアプリは、Entra Agent ID がプレビューの段階のため、実績のない構成要素（Microsoft Foundry Hosted Agent、Entra Agent ID の OBO フロー等）を複数含む。問題発生時に「確実に動作している部分」と「そうでない部分」を明確に切り分けられるよう、**各フェーズで 1 つの新しい概念だけを追加する**段階的な開発を行う。

### 1.2 フェーズ設計の原則

- **Phase 1 で作成した Identity Echo API は全フェーズを通して同一のものを使い続ける**（使い捨ての設定・実装を作らない）
- **Autonomous Flow を先に、Interactive Flow を後に実装する**（理由: Interactive FlowはAutonomous Flowより依存が多い）
- **SPA との統合を先に完成させてから Interactive Flow を追加する**（理由: SPA + Autonomous の統合が通れば、SPA側の問題は解消済みになる）
- Foundry Hosted Agent を最初から使う（MSI は Foundry Project System-Assigned MSI のみで完結し、使い捨てのリソースを作らない）

### 1.3 フェーズ一覧

| #           | フェーズ                                     | 新たに追加する概念                                                                 | 主な検証ポイント                                                |
| ----------- | -------------------------------------------- | ---------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| **Phase 1** | SPA + Identity Echo API                      | MSAL Auth Code Flow + PKCE、Bearer 認証                                            | CORS、App Registration、scope/audience                          |
| **Phase 2** | Hosted Agent 最小実装（Autonomous App Flow） | Foundry Hosted Agent、T1 取得、client_credentials、Backend API（テスト用最小構成） | Blueprint/Agent Identity/Federated Credential、T1 ロジック      |
| **Phase 3** | SPA + Autonomous App Flow 統合（E2E）        | Backend API、Managed Identity、SPA トリガー                                        | エンドツーエンドフロー                                          |
| **Phase 4** | Autonomous User Flow 追加                    | Agent User、user_fic                                                               | Agent User 設定、delegated 権限                                 |
| **Phase 5** | Interactive Flow                             | MSAL Tc 取得（Blueprint scope）、OBO（T1+Tc→TR）                                   | OBO 交換、Tc の audience、CORS（ブラウザ→Foundry 直接呼び出し） |
| **Phase 6** | LLM 整形・UI 最終化                          | System Prompt 充実、フロー可視化 UI                                                | LLM 品質、UX                                                    |

### 1.4 フェーズ間の依存関係

```text
Phase 1: SPA + Identity Echo API
    │
    ├──→ Phase 2: Hosted Agent 最小実装 (Autonomous App)
    │              │
    │              └──→ Phase 3: SPA 統合 (Autonomous App E2E)
    │                              │
    │                              └──→ Phase 4: Autonomous User Flow
    │                                              │
    │                                              └──→ Phase 5: Interactive Flow
    │                                                              │
    └──────────────────────────────────────────────────────────────┴──→ Phase 6: LLM 整形・UI
```

---

## 2. 各フェーズの詳細

---

### 2.0 プロジェクト構造（全フェーズ共通）

各フェーズの実装チェックリストで参照するファイルパスの前提となるディレクトリ構成を示す。

```text
src/
├── identity_echo_api/       # Phase 1〜: Identity Echo API（FastAPI）
│   ├── main.py
│   ├── config.py
│   ├── auth/
│   │   └── token_validator.py
│   └── routes/
│       └── resource.py
├── agent/                   # Phase 2〜: Foundry Hosted Agent（Python）
│   ├── main.py              # ChatAgent 定義 + from_agent_framework(agent).run()
│   ├── agent.yaml           # azd デプロイ用エージェント定義ファイル
│   ├── Dockerfile           # --platform linux/amd64 必須（linux/amd64 以外は起動不可）
│   ├── requirements.txt     # azure-ai-agentserver-agentframework, azure-identity, httpx
│   ├── config.py            # AgentConfig dataclass（環境変数サマリー）
│   ├── auth/
│   │   └── token_exchange.py    # T1/T2/TR 取得関数（get_t1, exchange_app_token 等）
│   └── tools/
│       ├── autonomous_app.py    (Phase 2 で追加, @ai_function)
│       ├── autonomous_user.py   (Phase 4 で追加, @ai_function)
│       └── interactive.py       (Phase 5 で追加, @ai_function)
├── backend_api/             # Phase 2〜: Backend API（FastAPI）
│   ├── main.py
│   ├── config.py
│   ├── foundry_client.py
│   └── routes/
│       └── demo.py
└── frontend/                # Phase 1〜: SPA（React + TypeScript）
    └── src/
        ├── authConfig.ts
        ├── App.tsx
        ├── api/
        │   ├── identityEchoApi.ts
        │   └── demoApi.ts           (Phase 3 で追加)
        └── components/
            ├── CallerInfo.tsx
            ├── ScenarioPanel.tsx       (Phase 3 で追加)
            ├── TokenFlowVisualizer.tsx  (Phase 6 で追加)
            ├── ScenarioComparison.tsx   (Phase 6 で追加)
            └── RawResponse.tsx          (Phase 6 で追加)
```

---

### Phase 1: SPA + Identity Echo API

#### 目的

Entra Agent ID を一切使わないシンプルな構成で、**MSAL.js の認証フローと Bearer トークン認証が正しく機能すること**を確立する。

> **デバッグ用実装の注記**: このフェーズで実装する「SPA から Identity Echo API への直接呼び出し」はトークン検証基盤の**疎通テスト（デバッグ）用**である。最終形では「SPA → Foundry Agent → Echo API」の流れになるため、フロントエンドの直接呼び出し部分は最終的に UI から隠すか、デバッグ用機能として扱う。

このフェーズで作成する Identity Echo API は後のすべてのフェーズで **同一のもの**を使い続ける。後々の「リソース API が誰からのアクセスと認識したか」の可視化はこの API が担う。

#### 追加するコンポーネント

| コンポーネント        | 役割                                                          | 実装            |
| --------------------- | ------------------------------------------------------------- | --------------- |
| **Frontend SPA**      | ユーザー認証（MSAL.js）、Identity Echo API 呼び出し、結果表示 | React + MSAL.js |
| **Identity Echo API** | Bearer トークンを受け取り、呼び出し元 identity 情報を返す     | Python FastAPI  |

#### 実装内容

**Frontend SPA**

- MSAL.js Auth Code Flow + PKCE（`PublicClientApplication`）
- スコープ: `api://{ResourceAPI_AppId}/CallerIdentity.Read`（Identity Echo API 固有のスコープ）
  - ※ Blueprint スコープ（`api://{BlueprintId}/access_agent`）はこの段階では不要
- 取得したトークンを `Authorization: Bearer <token>` ヘッダーに付与して Identity Echo API を呼び出す
- レスポンスを画面に表示する最小 UI

**Identity Echo API（`/api/resource`）**

- Bearer トークンを受け取り、JWT をデコードして呼び出し元情報を JSON で返す
- トークン検証項目:
  - 署名（Entra ID JWKS 公開鍵で RS256 検証）
  - `aud`（= Identity Echo API の App ID）
  - `iss`（= `https://login.microsoftonline.com/{tenantId}/v2.0`）
  - `exp`（有効期限）
- レスポンス例:

```json
{
  "resource": "Demo Protected Resource",
  "accessedAt": "2026-03-26T10:00:00Z",
  "caller": {
    "callerType": "delegated_human_user",
    "tokenKind": "delegated",
    "oid": "...",
    "upn": "alice@contoso.com",
    "appId": "...",
    "scopes": ["CallerIdentity.Read"],
    "roles": []
  },
  "humanReadable": "alice@contoso.com の委任権限 (CallerIdentity.Read) でアクセスされました"
}
```

> **レスポンス形式の詳細**（`displayName`, `appDisplayName`, `issuer`, `issuedAt`, `expiresAt` 等の追加フィールド）は設計書 §4.4 を参照。

**`callerType` の判定ロジック（確定版）**

受け取った JWT の claims から `callerType` を判定する（`AGENT_USER_UPN` 環境変数との照合で Agent User を識別）:

```python
def determine_caller_type(claims: dict, agent_user_upn: str) -> str:
    has_scp = bool(claims.get("scp"))
    if not has_scp:
        return "app_only"         # Application Permission（Autonomous App フロー）
    upn = claims.get("upn", "")
    if agent_user_upn and upn.lower() == agent_user_upn.lower():
        return "delegated_agent_user"  # Agent User（Autonomous User フロー）
    return "delegated_human_user"     # 人間ユーザー（Interactive フロー）
```

| TR の特徴                            | `callerType`           |
| ------------------------------------ | ---------------------- |
| `scp` なし、`roles` あり             | `app_only`             |
| `scp` あり、`upn` = `AGENT_USER_UPN` | `delegated_agent_user` |
| `scp` あり、`upn` ≠ `AGENT_USER_UPN` | `delegated_human_user` |

> `AGENT_USER_UPN` は Identity Echo API の環境変数として設定する（例: `agentuser@contoso.com`）。

#### App Registration（新規作成）

| 登録名                   | 種別                 | 設定                        |
| ------------------------ | -------------------- | --------------------------- |
| `demo-client-app`        | SPA（Public Client） | リダイレクト URI、PKCE 有効 |
| `demo-identity-echo-api` | Web API              | App ID URI、スコープ定義    |

> **スコープ設計方針**: Identity Echo API の App Registration には以下の**デモ専用スコープ**を定義する。Microsoft Graph 等の実際のリソースにアクセスせず、完結したデモ環境を構築できる。
>
> | スコープ                  | 種別                   | 使用フェーズ                                                       |
> | ------------------------- | ---------------------- | ------------------------------------------------------------------ |
> | `CallerIdentity.Read`     | Delegated Permission   | Phase 1（SPA）、Phase 4（Autonomous User）、Phase 5（Interactive） |
> | `CallerIdentity.Read.All` | Application Permission | Phase 2（Autonomous App）                                          |

#### 実装チェックリスト

**(1) Azure Portal — App Registration**

- [ ] `demo-identity-echo-api` App Registration を作成
  - App ID URI: `api://{Application ID}` を設定
  - Expose API → Scope: `CallerIdentity.Read`（Delegated）を追加
  - Expose API → App Role: `CallerIdentity.Read.All`（Application、値: `CallerIdentity.Read.All`）を追加
- [ ] `demo-client-app` App Registration を作成
  - Platform: SPA、Redirect URI: `http://localhost:3000` を設定
  - API Permissions: `CallerIdentity.Read`（Delegated）を追加し Admin Consent を実施

**(2) Identity Echo API（`src/identity_echo_api/`）**

- [ ] `src/identity_echo_api/config.py` — 環境変数（`TENANT_ID`、`IDENTITY_ECHO_API_CLIENT_ID`）
- [ ] `src/identity_echo_api/auth/token_validator.py` — JWT 検証ロジック
  - JWKS エンドポイントから公開鍵取得（`https://login.microsoftonline.com/{tenantId}/discovery/v2.0/keys`）
  - RS256 署名検証、`aud`（= `api://{IDENTITY_ECHO_API_CLIENT_ID}`）/ `iss` / `exp` 検証
- [ ] `src/identity_echo_api/routes/resource.py` — `GET /api/resource` エンドポイント
  - `Authorization: Bearer <token>` ヘッダー抽出 → 検証呼び出し
  - JWT クレームから `callerType` / `tokenKind` / `oid` / `upn` / `appId` / `scopes` / `roles` を組み立てて JSON レスポンス
- [ ] `src/identity_echo_api/main.py` — FastAPI アプリ、CORS ミドルウェア設定

**(3) Frontend SPA（`src/frontend/`）**

- [ ] `src/frontend/` に React プロジェクトを作成（Vite + TypeScript 推奨）
- [ ] `src/frontend/src/authConfig.ts` — MSAL `PublicClientApplication` 設定（`clientId`、`authority`、`redirectUri`、スコープ）
- [ ] `src/frontend/src/App.tsx` — ログイン / ログアウトボタン、認証済み UI の分岐
- [ ] `src/frontend/src/api/identityEchoApi.ts` — `getCallerInfo(accessToken: string)` 関数（`Authorization: Bearer` 付きで `GET /api/resource` を呼び出す）
- [ ] `src/frontend/src/components/CallerInfo.tsx` — レスポンス JSON を整形表示するコンポーネント

**(4) ローカル動作確認**

- [ ] Identity Echo API 起動 → トークンなし `GET /api/resource` が HTTP 401 を返すことを確認
- [ ] SPA でログイン → `CallerIdentity.Read` スコープのトークン取得を確認
- [ ] `GET /api/resource` に Bearer トークン付与 → `callerType: "delegated_human_user"` が返ることを確認

#### 切り分けポイント

| 問題                                      | 原因の候補                                               |
| ----------------------------------------- | -------------------------------------------------------- |
| MSAL のログインが動かない                 | リダイレクト URI の不一致、テナント ID の誤り            |
| トークンが Identity Echo API に拒否される | `aud` の不一致（`api://{wrong_app_id}`）、`iss` の不一致 |
| CORS エラー                               | Identity Echo API の CORS 設定漏れ                       |

---

### Phase 2: Foundry Hosted Agent 最小実装（Autonomous App Flow）

#### 目的

Foundry Hosted Agent のコンテナ内で **T1 取得 → TR 取得（client_credentials）→ Identity Echo API 呼び出し** を動作させる。

Entra Agent ID の設定（Blueprint / Agent Identity / Federated Credential）が正しいことを確立する最初のフェーズ。**SPA との統合はこのフェーズでは行わない**。

#### 追加するコンポーネント

| コンポーネント           | 役割                                            | 実装                                             |
| ------------------------ | ----------------------------------------------- | ------------------------------------------------ |
| **Foundry Hosted Agent** | T1 取得、TR 取得、Identity Echo API 呼び出し    | Python、Microsoft Agent Framework or custom code |
| **Backend API**（最小）  | Foundry Hosted Agent を呼び出すエントリポイント | Python FastAPI、Managed Identity                 |

#### Foundry Hosted Agent の実行環境と MSI

Foundry Hosted Agent は **Foundry が管理するコンテナ上で動作**する（サーバーサイド実行）。Function Tool を含むすべてのエージェントコードはこのコンテナ内で実行される。

MSI の扱い:

- **未公開エージェント**: Foundry プロジェクトの **System-Assigned MSI** が自動付与される（手動での UAMI 作成・アタッチ不要）
- **公開後**: Foundry が専用の Dedicated Agent Identity を自動プロビジョニングする

エージェントコード内では `DefaultAzureCredential()` を呼び出すだけで、Foundry がプロビジョニングした MSI トークンを自動取得できる。

#### 実装内容

**Foundry Hosted Agent（最小実装）**

LLM の整形は最小化し（system prompt を簡素に）、Function Tool の結果をほぼそのまま返す形で実装する。SDK は `azure-ai-agentserver-agentframework` を使用する。

**`main.py` 骨格（確定版）**

```python
import os
from agent_framework import ChatAgent
from agent_framework.azure import AzureAIAgentClient
from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity import DefaultAzureCredential
from tools.autonomous_app import call_resource_api_autonomous_app

agent = ChatAgent(
    chat_client=AzureAIAgentClient(
        project_endpoint=os.getenv("PROJECT_ENDPOINT"),
        model_deployment_name=os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-4o"),
        credential=DefaultAzureCredential(),
    ),
    instructions="...",  # Phase 6 で充実させる
    tools=[call_resource_api_autonomous_app],
)

if __name__ == "__main__":
    from_agent_framework(agent).run()  # localhost:8088 でローカルテスト可能
```

**`token_exchange.py` — HTTP パラメータ（確定版）**

共通定数:

```python
ENTRA_TOKEN_ENDPOINT = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
TOKEN_EXCHANGE_SCOPE = "api://AzureADTokenExchange/.default"
CLIENT_ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
```

`get_t1()` — T1 取得（全フロー共通、MSI を FIC として Blueprint に提示）:

```text
POST /oauth2/v2.0/token
client_id             = {blueprint_client_id}   # Blueprint の Application ID
scope                 = api://AzureADTokenExchange/.default
fmi_path              = {agent_identity_oid}    # Agent Identity の Service Principal OID
client_assertion_type = urn:...:jwt-bearer
client_assertion      = {msi_token}             # DefaultAzureCredential().get_token(...)
grant_type            = client_credentials
```

> 返却: T1 (aud = Blueprint)。`fmi_path` には Agent Identity の Service Principal OID を指定。

`exchange_app_token()` — Autonomous App TR 取得（app-only）:

```text
POST /oauth2/v2.0/token
client_id             = {agent_identity_oid}
scope                 = {resource_api_default_scope}  # api://{id}/.default（client_credentials では /.default 必須）
client_assertion_type = urn:...:jwt-bearer
client_assertion      = {t1}
grant_type            = client_credentials
```

> 返却: TR (app-only, roles あり, scp なし, sub = Agent Identity OID)
> **注**: `client_credentials` grant type では scope に `/.default` サフィックスが必須。具体スコープ名（`CallerIdentity.Read.All`）を直接指定すると Entra ID がエラーを返す。Delegated フロー（Interactive / Autonomous User）では具体スコープ `api://{id}/CallerIdentity.Read` を指定する。

**`tools/autonomous_app.py`（`@ai_function` デコレータ必須）**

```python
from agent_framework import ai_function

@ai_function
def call_resource_api_autonomous_app() -> str:
    """Autonomous App フローでリソース API を呼び出す"""
    t1 = get_t1()
    tr = exchange_app_token(t1=t1)
    return call_resource_api(bearer_token=tr)
```

**`requirements.txt`**:

```text
azure-ai-agentserver-agentframework
azure-identity
httpx
python-dotenv
```

**`Dockerfile`**（`--platform linux/amd64` 必須）:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8088
CMD ["python", "main.py"]
```

**`agent.yaml`**（azd デプロイ用最小骨格）:

```yaml
name: demo-entra-agent-id
image: ${ACR_NAME}.azurecr.io/demo-entra-agent-id:latest
cpu: 1
memory: 2Gi
environmentVariables:
  PROJECT_ENDPOINT: ${PROJECT_ENDPOINT}
  MODEL_DEPLOYMENT_NAME: gpt-4o
  BLUEPRINT_CLIENT_ID: ${BLUEPRINT_CLIENT_ID}
  AGENT_IDENTITY_OID: ${AGENT_IDENTITY_OID}
  RESOURCE_API_URL: ${RESOURCE_API_URL}
  RESOURCE_API_SCOPE: ${RESOURCE_API_SCOPE}
  RESOURCE_API_DEFAULT_SCOPE: ${RESOURCE_API_DEFAULT_SCOPE}
  TENANT_ID: ${TENANT_ID}
```

**`config.py`**（環境変数サマリー）:

```python
import os
from dataclasses import dataclass

@dataclass
class AgentConfig:
    tenant_id: str            = os.getenv("TENANT_ID", "")
    blueprint_client_id: str  = os.getenv("BLUEPRINT_CLIENT_ID", "")  # Blueprint Application ID
    agent_identity_oid: str   = os.getenv("AGENT_IDENTITY_OID", "")   # fmi_path 兼 client_id
    agent_user_oid: str       = os.getenv("AGENT_USER_OID", "")       # user_fic の user_id
    agent_user_upn: str       = os.getenv("AGENT_USER_UPN", "")       # callerType 判定用
    resource_api_url: str           = os.getenv("RESOURCE_API_URL", "")
    resource_api_scope: str         = os.getenv("RESOURCE_API_SCOPE", "")           # delegated 用: api://{id}/CallerIdentity.Read
    resource_api_default_scope: str = os.getenv("RESOURCE_API_DEFAULT_SCOPE", "")   # app-only 用: api://{id}/.default
    project_endpoint: str     = os.getenv("PROJECT_ENDPOINT", "")

config = AgentConfig()
```

**Backend API（最小実装）**

```text
POST /api/demo/autonomous/app
  → Foundry Hosted Agent を呼び出し、レスポンスを返す
  （この段階ではフロントエンドとの統合なし、curl や REST クライアントで直接テスト）
```

#### Azure / Entra ID 設定（新規）

| 設定項目                        | 内容                                                           |
| ------------------------------- | -------------------------------------------------------------- |
| Agent Identity Blueprint        | Foundry Project が Publish 時に自動生成（手動設定不要）        |
| Agent Identity                  | 同上（Foundry が自動生成）                                     |
| Federated Credential            | Foundry Project MSI ↔ Blueprint の紐付け（Foundry が自動設定） |
| Identity Echo API の App Role   | Agent Identity に Application Permission を付与                |
| Backend API の Managed Identity | Foundry Cognitive Services User ロールを付与                   |

> **重要**: Blueprint・Agent Identity・Federated Credential は Foundry が Agent を Publish する際に**自動プロビジョニングされる**。手動での Entra ID 操作は Identity Echo API への Permission 付与のみ。

#### テスト方法

この段階では SPA なしで、curl または REST クライアントから Backend API を直接呼び出してテストする。

```http
POST https://{backend-api}/api/demo/autonomous/app

# 期待するレスポンス
{
  "caller": {
    "callerType": "app_only",
    "oid": "{Agent Identity の OID}",
    "appId": "{Agent Identity の App ID}"
  }
}
```

#### 実装チェックリスト

**(1) Microsoft Foundry — Hosted Agent の雛形作成**

- [ ] Foundry Project を作成（Azure Portal / Foundry Studio）
- [ ] Foundry Studio で Hosted Agent（Python）を新規作成（System prompt は仮で最小化しておく）

**(2) Hosted Agent のコーディング（`src/agent/`）**

- [ ] `src/agent/config.py` — `AgentConfig` dataclass（環境変数: `BLUEPRINT_CLIENT_ID`, `AGENT_IDENTITY_OID`, `RESOURCE_API_SCOPE`, `RESOURCE_API_DEFAULT_SCOPE`, `RESOURCE_API_URL` 等）
- [ ] `src/agent/auth/token_exchange.py` — T1・TR 取得ロジック
  - `get_t1()` — `DefaultAzureCredential().get_token()` で MSI TOKEN を取得し、`client_credentials` + `fmi_path` で T1 を取得
  - `exchange_app_token(t1)` — T1 → TR（`client_credentials`、app-only、scope = `RESOURCE_API_DEFAULT_SCOPE`）
- [ ] `src/agent/tools/autonomous_app.py` — `call_resource_api_autonomous_app()` Function Tool（`@ai_function` デコレータ必須）
- [ ] `src/agent/main.py` — `ChatAgent` + `from_agent_framework(agent).run()` エントリポイント（`azure-ai-agentserver-agentframework` 使用）
- [ ] `src/agent/requirements.txt` — `azure-ai-agentserver-agentframework`, `azure-identity`, `httpx`, `python-dotenv`
- [ ] `src/agent/Dockerfile` — `FROM python:3.11-slim`、`EXPOSE 8088`（`--platform linux/amd64` でビルド必須）
- [ ] `src/agent/agent.yaml` — azd デプロイ用定義ファイル（image, cpu, memory, environmentVariables）

**(3) Agent の Publish → 自動プロビジョニング確認**

- [ ] Foundry Studio から Agent を Publish
- [ ] Entra ID に Blueprint Application が自動生成されたことを確認（Portal > App Registrations）
- [ ] Entra ID に Agent Identity（Service Principal）が自動生成されたことを確認
- [ ] Federated Credential（Project MSI ↔ Blueprint）が自動設定されたことを確認

**(4) Azure Portal — 権限設定**

- [ ] Agent Identity に `CallerIdentity.Read.All`（Application Permission）を付与
  - `demo-identity-echo-api` > Enterprise Applications > Agent Identity を検索 > Add Permission
- [ ] Backend API の Managed Identity に `Cognitive Services User` ロールを付与（Foundry Project スコープで）

**(5) Backend API の最小実装（`src/backend_api/`）**

- [ ] `src/backend_api/config.py` — 環境変数（`FOUNDRY_AGENT_ENDPOINT`、`TENANT_ID` 等）
- [ ] `src/backend_api/foundry_client.py` — Foundry Agent API 呼び出しクライアント（MSI token 使用）
- [ ] `src/backend_api/routes/demo.py` — `POST /api/demo/autonomous/app` エンドポイント（Foundry Agent API を呼び出し Function Tool 結果を返す）
- [ ] `src/backend_api/main.py` — FastAPI アプリ（CORS は Phase 3 まで不要）

**(6) curl / REST クライアントでのテスト**

- [ ] `POST /api/demo/autonomous/app` に curl → `callerType: "app_only"` と Agent Identity OID が返ることを確認

#### 切り分けポイント

| 問題                                   | 原因の候補                                           |
| -------------------------------------- | ---------------------------------------------------- |
| T1 取得が失敗する                      | Federated Credential の設定誤り、MSI の権限不足      |
| TR 取得が失敗する                      | Agent Identity の Application Permission 未付与      |
| Identity Echo API がトークンを拒否する | `aud` の誤り（Identity Echo API の App ID と不一致） |
| `callerType` が `app_only` にならない  | TR 取得フローが client_credentials になっていない    |

#### SDK・MSI 対応（確認済み事項）

公式ドキュメント ([What are hosted agents?](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)) により以下が確認済みのため、実装前の調査は不要：

- **`azure-identity` による MSI 認証は可能**。Foundry Hosted Agent のコンテナには System-Assigned MSI が自動付与されており、`DefaultAzureCredential()` で透過的にトークンを取得できる。UAMI の手動作成・アタッチは不要。
- **SDK は `azure-ai-projects 2.x`（Responses API / Agents v2）**。旧 Assistants API v1 の Thread/Run/Message から Conversation/Response/Item に用語が変更されている。詳細は [azure-ai-projects SDK ドキュメント](https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/sdk-overview) を参照。

---

### Phase 3: SPA + Autonomous App Flow 統合（E2E）

#### 目的

Phase 1 の SPA と Phase 2 の Backend API + Foundry Hosted Agent を接続し、**Autonomous App Flow のエンドツーエンドを完成させる**。

#### 追加・変更するコンポーネント

| コンポーネント   | 変更内容                                            |
| ---------------- | --------------------------------------------------- |
| **Frontend SPA** | Autonomous シナリオ用のトリガー UI と結果表示を追加 |
| **Backend API**  | CORS 設定、フロントエンドからのリクエスト受付を追加 |

#### 実装内容

**Frontend SPA 変更点**

- Autonomous App シナリオの選択 UI を追加
- 実行ボタン → `POST /api/demo/autonomous/app` を呼び出す（認証トークン不要）
- レスポンス（`callerType`, `upn`, `oid` 等）を画面に表示

**Backend API 変更点**

- CORS 設定（SPA のオリジンを許可）
- フロントエンドからのリクエストを受け付けて Foundry Agent API を呼び出す
- エラーハンドリング、レスポンスのフロントエンドへの転送

#### 完成する E2E フロー

```text
👤 ユーザー
  → [実行ボタン] → SPA
  → POST /api/demo/autonomous/app → Backend API (MSI token)
  → Foundry Hosted Agent
      → T1 取得 (Project MSI) → TR 取得 (client_credentials)
      → GET /api/resource (Bearer TR) → Identity Echo API
  ← { callerType: "app_only", oid: "Agent Identity OID" }
  ← LLM 整形 → Backend API → SPA → 画面表示
```

> 詳細なシーケンスは設計書 §5.2 を参照。

#### 実装チェックリスト

**(1) Backend API の変更（`src/backend_api/`）**

- [ ] `src/backend_api/main.py` に CORS ミドルウェアを追加（許可オリジン: SPA のローカルアドレス + 本番 URL）
- [ ] タイムアウト・エラーハンドリング（Foundry Agent API 呼び出し失敗時の 500 エラー整形）

**(2) Frontend SPA の変更（`src/frontend/`）**

- [ ] `src/frontend/src/api/demoApi.ts` を新規作成し `runAutonomousApp()` 関数を追加（`POST /api/demo/autonomous/app` を呼び出す、認証トークン不要）
- [ ] `src/frontend/src/components/ScenarioPanel.tsx` を新規作成（シナリオ選択 + 実行ボタン UI）
- [ ] `src/frontend/src/components/CallerInfo.tsx` を Autonomous App のレスポンスも表示できるよう拡張
- [ ] `src/frontend/src/App.tsx` に ScenarioPanel を組み込み

**(3) E2E 動作確認**

- [ ] SPA の実行ボタン → Backend API → Foundry Agent → Identity Echo API の E2E が通ることを確認
- [ ] 画面に `callerType: "app_only"`、Agent Identity OID が表示されることを確認

#### 切り分けポイント

| 問題                                            | 原因の候補                                                              |
| ----------------------------------------------- | ----------------------------------------------------------------------- |
| フロントエンドから Backend API がブロックされる | CORS 設定漏れ                                                           |
| Backend API の MSI が Foundry を呼び出せない    | Backend API の Managed Identity に Cognitive Services User ロール未付与 |

---

### Phase 4: Autonomous User Flow 追加

#### 目的

Phase 3 の Autonomous App Flow に加えて、**Agent User の委任権限で動作する Autonomous User Flow** を追加する。「自律エージェントでも delegated 権限を使える」というコンセプトを実装する。

#### 追加するコンセプト

| コンセプト                     | 内容                                                                                                                     |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| **Agent User**                 | Entra ID テナント内の専用ユーザーアカウント（`agentuser@contoso.com`）。エージェントを代理するユーザー ID として機能する |
| **Agent User FIC（user_fic）** | T1 + T2 を使って Agent User の委任権限を持つ TR を取得するフロー（`grant_type=user_fic`。OBO ではない）                  |

#### 実装内容

**Foundry Hosted Agent 変更点**

Autonomous App Flow の Function Tool に並んで、Autonomous User Flow 用の Function Tool を追加する。

```python
# Function Tool: call_resource_api_autonomous_user()
@ai_function
def call_resource_api_autonomous_user() -> str:
    """Autonomous User フローでリソース API を呼び出す"""
    t1 = get_t1()                          # get_t1(): 全フロー共通
    t2 = get_t2(t1=t1)                     # get_t2(): Agent Identity Exchange Token
    tr = exchange_agent_user_token(        # user_fic grant type で Agent User TR を取得
        t1=t1,
        t2=t2,
        user_id=config.agent_user_oid,     # Agent User の Object ID（UPN ではなく OID）
    )
    return call_resource_api(bearer_token=tr)
```

**`token_exchange.py` 追加関数 — HTTP パラメータ（確定版）**

`get_t2()` — Agent Identity Exchange Token（T2）取得:

```text
POST /oauth2/v2.0/token
client_id             = {agent_identity_oid}
scope                 = api://AzureADTokenExchange/.default
client_assertion_type = urn:...:jwt-bearer
client_assertion      = {t1}
grant_type            = client_credentials
```

> 返却: T2 (aud = Agent Identity, Agent User FIC として使用)

`exchange_agent_user_token()` — `user_fic` grant type で Agent User TR 取得:

```text
POST /oauth2/v2.0/token
client_id                          = {agent_identity_oid}
scope                              = {resource_api_scope}
grant_type                         = user_fic
client_assertion_type              = urn:...:jwt-bearer
client_assertion                   = {t1}
user_id                            = {agent_user_oid}  # Object ID（UPN ではなく OID）
user_federated_identity_credential = {t2}
```

> 返却: TR (delegated, sub = Agent User OID, upn = Agent User UPN)
> **注**: `grant_type=user_fic` は Agent User 専用。OBO (`jwt-bearer`) ではない（リポジトリ内 `src/api/get-autonomous-agent-user-token.http` で確認済み）。

**Frontend SPA / Backend API 変更点**

- `POST /api/demo/autonomous/user` エンドポイントを追加（Backend API）
- Autonomous User Flow の選択 UI を追加（SPA）

#### Azure / Entra ID 設定（新規）

| 設定項目                       | 内容                                      |
| ------------------------------ | ----------------------------------------- |
| Agent User アカウント          | テナントに `agentuser@contoso.com` を作成 |
| Identity Echo API への委任権限 | Agent User に対してスコープ同意を付与     |

#### 期待するレスポンス

```json
{
  "caller": {
    "callerType": "delegated_agent_user",
    "tokenKind": "delegated",
    "upn": "agentuser@contoso.com"
  }
}
```

#### 実装チェックリスト

**(1) Azure Portal — Agent User 設定**

- [ ] テナントに `agentuser@contoso.com` ユーザーを作成（Entra ID > Users）
- [ ] `demo-identity-echo-api` の `CallerIdentity.Read`（Delegated）に対して `agentuser@contoso.com` の同意を付与

**(2) Hosted Agent の変更（`src/agent/`）**

- [ ] `src/agent/auth/token_exchange.py` に `get_t2(t1)` と `exchange_agent_user_token(t1, t2, user_id)` を追加（`grant_type=user_fic` で Agent User TR を取得）
- [ ] `src/agent/tools/autonomous_user.py` を新規作成し `call_resource_api_autonomous_user()` Function Tool を実装（`@ai_function` デコレータ）
- [ ] `src/agent/config.py` に `AGENT_USER_UPN` 環境変数を追加
- [ ] `src/agent/agent.yaml` の `environmentVariables` に `AGENT_USER_OID` と `AGENT_USER_UPN` を追加
- [ ] `src/agent/main.py` に新 Function Tool を登録

**(3) Backend API の変更（`src/backend_api/`）**

- [ ] `src/backend_api/routes/demo.py` に `POST /api/demo/autonomous/user` エンドポイントを追加

**(4) Frontend SPA の変更（`src/frontend/`）**

- [ ] `src/frontend/src/api/demoApi.ts` に `runAutonomousUser()` 関数を追加
- [ ] `src/frontend/src/components/ScenarioPanel.tsx` の選択肢に Autonomous User シナリオを追加

**(5) 動作確認**

- [ ] `POST /api/demo/autonomous/user` → `callerType: "delegated_agent_user"`、`upn: "agentuser@contoso.com"` を確認

#### 切り分けポイント

| 問題                                 | 原因の候補                                                                                        |
| ------------------------------------ | ------------------------------------------------------------------------------------------------- |
| Agent User FIC（user_fic）が失敗する | Agent User への委任権限の同意が未設定                                                             |
| `callerType` が `app_only` になる    | user_fic フローではなく client_credentials になっている                                           |
| `upn` が Agent User のものにならない | user_fic のパラメータ（`user_id` / `user_federated_identity_credential`）が正しく設定されていない |

---

### Phase 5: Interactive Flow

#### 目的

**人間ユーザー自身の委任権限**で、エージェントがリソース API を呼び出す Interactive Flow を実装する。OBO（T1 + Tc → TR）の実装を追加する。

#### 前提条件

- Phase 1: SPA の MSAL 認証が動作している ✅
- Phase 2: Hosted Agent での T1 取得が動作している ✅
- Phase 3: SPA → Backend API → Foundry Agent の E2E が動作している ✅

これらが揃った状態で OBO の実装だけを追加するため、問題発生時の切り分けが容易になる。

#### Interactive Flow のアーキテクチャ

Interactive Flow では、SPA が **Foundry Agent API を直接呼び出す**（Autonomous Flow とは異なり Backend API を経由しない）。

```text
SPA (ブラウザ)
  → MSAL で 2 トークンを取得:
      (1) Tc: scope = api://{BlueprintId}/access_agent (OBO の入力トークン)
      (2) Foundry API トークン: scope = https://cognitiveservices.azure.com/.default
  → Foundry Agent API を直接呼び出す:
      Authorization: Bearer {Foundry API トークン}
      message payload に Tc を埋め込む
  → Foundry Hosted Agent が Tc を使って OBO を実行:
      T1 + Tc → TR (sub = alice@contoso.com)
  → Identity Echo API → { callerType: "delegated_human_user", upn: "alice@..." }
```

> ⚠️ **CORS リスクポイント**: ブラウザから Foundry Agent API を直接呼び出すため、Foundry Agent Service エンドポイントが CORS を許可しているか事前に確認・検証が必要。

#### 実装内容

**Frontend SPA 変更点**

- Interactive シナリオ用の MSAL スコープを追加:
  - `api://{BlueprintId}/access_agent`（Tc 取得用）
  - `https://cognitiveservices.azure.com/.default`（Foundry API 呼び出し用）
- Interactive シナリオ選択時はログインを促す UI を追加
- Foundry Agent API への直接呼び出し実装

```javascript
// Interactive Flow: 2種類のトークンを取得
const tc = await msalInstance.acquireTokenSilent({
  scopes: [`api://${BLUEPRINT_APP_ID}/access_agent`],
});
const foundryToken = await msalInstance.acquireTokenSilent({
  scopes: ["https://cognitiveservices.azure.com/.default"],
});

// Foundry Agent API を直接呼び出し（Tc はペイロードに埋め込む）
const response = await fetch(FOUNDRY_AGENT_ENDPOINT, {
  headers: { Authorization: `Bearer ${foundryToken.accessToken}` },
  body: JSON.stringify({ input: `run_interactive tc=${tc.accessToken}` }),
});
```

**Foundry Hosted Agent 変更点**

- Interactive Flow 用の Function Tool を追加:

```python
# Function Tool: call_resource_api_interactive(tc: str)
@ai_function
def call_resource_api_interactive(tc: str) -> str:
    """Interactive フローでリソース API を呼び出す（Tc はメッセージ本文から受け取る）"""
    t1 = get_t1()                    # 全フロー共通
    tr = exchange_interactive_obo(   # OBO: T1 + Tc → TR (sub = 人間ユーザー)
        t1=t1,
        tc=tc,
    )
    return call_resource_api(bearer_token=tr)
```

**`token_exchange.py` 追加関数 — HTTP パラメータ（確定版）**

`exchange_interactive_obo()` — OBO で人間ユーザー委任 TR を取得:

```text
POST /oauth2/v2.0/token
client_id             = {agent_identity_oid}
scope                 = {resource_api_scope}
client_assertion_type = urn:...:jwt-bearer
client_assertion      = {t1}
assertion             = {tc}                     # aud=Blueprint, sub=人間ユーザー
grant_type            = urn:ietf:params:oauth:grant-type:jwt-bearer
requested_token_use   = on_behalf_of
```

> 返却: TR (delegated, sub = Tc の sub = 人間ユーザー OID, upn = 人間ユーザー UPN)

**Backend API は Interactive Flow に非介在**

Interactive Flow では SPA が Foundry Agent API を直接呼び出すため、Backend API は関与しない。Tc はメッセージペイロードに埋め込んで Foundry Agent に渡す。これにより Backend API でのセッション管理（Redis 等）は不要となる。

> **補足**: `azure-ai-projects` の `responses.create()` は blocking（同期）呼び出しのためポーリング不要。Autonomous Flow で使用する Backend API の全エンドポイントは同期モデルを採用する。

#### ユーザー同意（Step B）

デモ環境での推奨方針は**管理者事前同意（Admin Consent）** を使い、Step B（ユーザーごとの同意）をスキップすること。ただし、Entra Agent ID の同意フローを見せることもデモの教育価値があるため、オプションとして「同意フローあり版」を用意することを検討する。初回の同意フローをデモに含める場合は同意 URL の生成ロジックも実装する。

#### Tc のセキュリティ考慮事項

Interactive Flow では SPA が Foundry Agent API を直接呼び出し、Tc をメッセージペイロードに埋め込んで渡す。Backend API は経由しない。

| 課題                    | 対策                                                                                |
| ----------------------- | ----------------------------------------------------------------------------------- |
| Tc の転送経路           | HTTPS 必須（Foundry Agent API エンドポイントは HTTPS）                              |
| Tc の有効期間           | Entra ID が発行する短寿命トークン（通常 1 時間）をそのまま利用                      |
| Resource API の認可     | JWT 署名検証（JWKS）＋ `aud` 検証を厳格に実施                                       |
| Tc のメッセージ埋め込み | Foundry Agent のメッセージペイロードは TLS で暗号化されており、デモ用途では許容範囲 |

#### App Registration 変更点

| 変更先                                | 変更内容                                   |
| ------------------------------------- | ------------------------------------------ |
| `demo-client-app` の API アクセス設定 | Blueprint スコープ（`access_agent`）を追加 |
| Blueprint Application                 | SPA の App ID に対して同意を許可           |

#### 期待するレスポンス

```json
{
  "caller": {
    "callerType": "delegated_human_user",
    "tokenKind": "delegated",
    "upn": "alice@contoso.com"
  }
}
```

#### 実装チェックリスト

**(1) Azure Portal — App Registration 変更**

- [ ] `demo-client-app` の API アクセスに Blueprint の `access_agent` スコープを追加
- [ ] Blueprint Application（Entra ID > Enterprise Applications）で `demo-client-app` の App ID からの同意を許可（Admin Consent）

**(2) Hosted Agent の変更（`src/agent/`）**

- [ ] `src/agent/auth/token_exchange.py` に `exchange_interactive_obo(t1, tc)` を追加（T1 + Tc → TR、OBO grant type、sub = 人間ユーザー）
- [ ] `src/agent/tools/interactive.py` を新規作成し `call_resource_api_interactive(tc: str)` Function Tool を実装（`@ai_function` デコレータ）
- [ ] `src/agent/main.py` に新 Function Tool を登録

**(3) Frontend SPA の変更（`src/frontend/`）**

- [ ] `src/frontend/src/authConfig.ts` に Blueprint スコープ（`api://{BlueprintId}/access_agent`）を追加
- [ ] `src/frontend/src/api/demoApi.ts` に `runInteractive()` 関数を追加
  - Tc（`access_agent` scope）と Foundry API トークン（`cognitiveservices.azure.com/.default`）の 2 トークンを取得
  - Foundry Agent API を直接呼び出し（`Authorization: Bearer {foundryToken}`、Tc はペイロードに埋め込む）
- [ ] Interactive シナリオ選択時にログインを促すガード UI を追加
- [ ] `src/frontend/src/components/ScenarioPanel.tsx` に Interactive シナリオを追加

**(4) CORS 事前確認**

- [ ] ブラウザ DevTools で Foundry Agent API エンドポイントへの `OPTIONS` リクエストを確認し CORS エラーがないことを確認

**(5) 動作確認**

- [ ] Interactive シナリオ実行 → `callerType: "delegated_human_user"`、`upn: "{ログイン中ユーザー}"` を確認

#### 切り分けポイント

| 問題                                     | 原因の候補                                                     |
| ---------------------------------------- | -------------------------------------------------------------- |
| MSAL で Tc（Blueprint scope）が取れない  | Blueprint の App Registration の設定誤り、スコープ未公開       |
| Foundry Agent API 呼び出しが CORS エラー | Foundry エンドポイントの CORS 設定不備（Phase 5 固有のリスク） |
| OBO 交換が失敗する                       | Tc の `aud` が Blueprint の App ID と不一致                    |
| TR の sub がユーザーにならない           | OBO ではなく別のフローが実行されている（実装誤り）             |

---

### Phase 6: LLM 整形・UI 最終化

#### 目的

Phase 2〜5 で最小化していた LLM の整形機能を充実させ、**技術者・非技術者の両方が理解できるデモ体験**を完成させる。

#### 実装内容

**Foundry Hosted Agent の System Prompt 充実**

```text
あなたは Microsoft Entra Agent ID のデモエージェントです。
リソース API を呼び出した後、以下を日本語で分かりやすく説明してください：

1. 今回のシナリオで「誰の権限で」API にアクセスしたか
2. どのトークン取得フローが実行されたか（使用したトークン種別）
3. リソース API が認識した呼び出し元の情報
4. このアクセスパターンがどのようなユースケースに適しているか

技術者・非技術者の両方が理解できるよう、専門用語は適宜補足説明を加えてください。
```

**Frontend UI の充実**

設計書 §4.1 の画面レイアウトに基づき、以下を追加:

- **トークンフロー可視化パネル**: 現在実行中のステップをハイライト
- **3 シナリオ比較表**: 実行後に 3 シナリオの caller 情報を横並びで比較
- **生レスポンス表示**: リソース API の生 JSON を折りたたみ表示

#### 同時実行への対応

3 シナリオを並べて実行する「比較モード」では、同時に 3 つの Foundry Agent Session が走る可能性がある。Backend API のスレッド管理とタイムアウト処理をこのフェーズで対応する：

- 非同期エンドポイント（FastAPI `async def`）によるノンブロッキング処理
  - **Memo**: 完全なノンブロッキング性を求める場合、Azure 認証処理にも同期的ブロッキングが発生しないよう `azure.identity.aio` の `DefaultAzureCredential` の使用を検討すると、同時実行時のパフォーマンスが安定する。
- 各シナリオへのタイムアウト設定（例: 60 秒）
- エラーハンドリング：いずれか 1 シナリオが失敗しても他 2 つは表示できるよう独立した状態管理

#### 実装チェックリスト

**(1) Foundry Hosted Agent の更新（`src/agent/`）**

- [ ] `src/agent/main.py` の system prompt を Phase 6 の内容に更新（3 シナリオ共通の説明テンプレート）

**(2) Frontend UI の充実（`src/frontend/`）**

- [ ] `src/frontend/src/components/TokenFlowVisualizer.tsx` — 実行中のステップをハイライトするパネル
- [ ] `src/frontend/src/components/ScenarioComparison.tsx` — 3 シナリオの caller 情報を横並び比較する表コンポーネント
- [ ] `src/frontend/src/components/RawResponse.tsx` — 生 JSON を折りたたみ表示するコンポーネント
- [ ] `src/frontend/src/App.tsx` に 3 シナリオ同時実行「比較モード」UI を追加

**(3) Backend API の非同期化・タイムアウト対応（`src/backend_api/`）**

- [ ] 全ルートハンドラを `async def` に変更（`httpx.AsyncClient` でノンブロッキング化）
- [ ] Foundry Agent API 呼び出しに 60 秒タイムアウトを設定
- [ ] 3 シナリオの状態を独立したレスポンスモデルで管理し、1 シナリオのエラーが他に影響しない実装

**(4) 最終 E2E テスト**

- [ ] 3 シナリオを同時実行（比較モード）して全シナリオが独立して動作することを確認
- [ ] LLM の説明文（日本語）が適切であることを確認
- [ ] エラーシナリオ（Foundry タイムアウト等）のフォールバック表示を確認

---

## 3. App Registration・Azure リソース まとめ

### フェーズごとの追加リソース

| フェーズ | App Registration / Azure リソース                                                         | 用途                              |
| -------- | ----------------------------------------------------------------------------------------- | --------------------------------- |
| Phase 1  | `demo-client-app`（SPA）、`demo-identity-echo-api`（API）                                 | MSAL 認証、Bearer 検証            |
| Phase 2  | Foundry Project（→ Blueprint/Agent Identity を自動生成）、Backend API（Managed Identity） | Hosted Agent 実行環境、T1/TR 取得 |
| Phase 3  | 追加なし（Backend API に CORS 設定を追加）                                                | -                                 |
| Phase 4  | Agent User アカウント（`agentuser@contoso.com`）                                          | Autonomous User Flow              |
| Phase 5  | `demo-client-app` の API アクセス設定に Blueprint スコープを追加                          | Interactive Flow Tc 取得          |
| Phase 6  | 追加なし                                                                                  | -                                 |

### Foundry の自動プロビジョニングにより手動設定不要なもの

- Agent Identity Blueprint
- Agent Identity（Service Principal）
- Federated Credential（Foundry Project MSI ↔ Blueprint）
- Hosted Agent の System-Assigned MSI（未公開時）／Dedicated Agent Identity（公開後）

---

## 4. Azure デプロイ構成

### 4.1 コンポーネント別デプロイ先

| コンポーネント        | Azure サービス            | SKU         | 選定理由                                                                                                   |
| --------------------- | ------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------- |
| **Frontend SPA**      | Azure Static Web Apps     | Free        | 静的ファイル配信・CDN 内蔵・HTTPS URL 自動発行・GitHub Actions CI/CD 標準統合                              |
| **Identity Echo API** | Azure Container Apps      | Consumption | コンテナ化 FastAPI に適合・スケールゼロ対応・将来的に Internal Ingress 化可能                              |
| **Backend API**       | Azure Container Apps      | Consumption | **Managed Identity が必須**（Foundry Agent API の MSI 呼び出しに必要）・Identity Echo API と同一運用モデル |
| **Foundry Agent**     | Microsoft Foundry Project | Standard    | Hosted Agent のコンテナ実行環境・MSI 自動付与・Blueprint/Agent Identity 自動生成                           |

### 4.2 フェーズごとのデプロイタスク

#### Phase 1 デプロイ

- [ ] Azure Static Web Apps リソースを作成し、SPA の Redirect URI（HTTPS）を Entra ID `demo-client-app` に追加登録
- [ ] Identity Echo API の `Dockerfile` を作成（Python + uvicorn ベースイメージ）
- [ ] Azure Container Apps 環境（Environment）を作成
- [ ] Identity Echo API コンテナを Container Apps にデプロイ
- [ ] Identity Echo API の CORS 許可オリジンに Static Web Apps の URL を設定
- [ ] SPA を Static Web Apps にデプロイ（`npm run build` → Azure CLI or GitHub Actions）
- [ ] デプロイ後 E2E 確認: SPA ログイン → Identity Echo API 呼び出し → `callerType: "delegated_human_user"` を確認

#### Phase 2 デプロイ

- [ ] Backend API の `Dockerfile` を作成
- [ ] Backend API を同一 Container Apps 環境にデプロイ
- [ ] Backend API の Container App で **System-Assigned Managed Identity を有効化**
- [ ] Backend API の Managed Identity に Foundry Project スコープで `Cognitive Services User` ロールを付与
- [ ] デプロイ後確認: `POST /api/demo/autonomous/app` に curl → `callerType: "app_only"` を確認

#### Phase 3 デプロイ

- [ ] Backend API の CORS 許可オリジンに Static Web Apps の URL を追加して再デプロイ
- [ ] SPA に Autonomous App シナリオ UI を追加して再デプロイ
- [ ] デプロイ後 E2E 確認: SPA 実行ボタン → Backend API → Foundry Agent → Identity Echo API の順に動作を確認

#### Phase 4 デプロイ

- [ ] Backend API に `POST /api/demo/autonomous/user` エンドポイントを追加して再デプロイ
- [ ] SPA に Autonomous User シナリオ UI を追加して再デプロイ

#### Phase 5 デプロイ

- [ ] SPA に Interactive シナリオ UI（Foundry Agent 直接呼び出し）を追加して再デプロイ
- [ ] CORS 事前確認: Foundry Agent API エンドポイントへのブラウザからの `OPTIONS` リクエストが通ることを確認

#### Phase 6 デプロイ

- [ ] Backend API の全ルートハンドラを `async def` に変更して再デプロイ
- [ ] SPA にトークンフロー可視化・比較モード UI を追加して再デプロイ

### 4.3 環境変数まとめ

| コンポーネント       | 変数名                        | 設定値の例 / 取得元                                                                |
| -------------------- | ----------------------------- | ---------------------------------------------------------------------------------- |
| Identity Echo API    | `TENANT_ID`                   | Entra ID テナント ID                                                               |
| Identity Echo API    | `IDENTITY_ECHO_API_CLIENT_ID` | `demo-identity-echo-api` App Registration の Client ID                             |
| Identity Echo API    | `AGENT_USER_UPN`              | `agentuser@contoso.com`（callerType 判定用、Phase 4 以降）                         |
| Backend API          | `FOUNDRY_AGENT_ENDPOINT`      | Foundry Studio のエージェントエンドポイント URL                                    |
| Backend API          | `TENANT_ID`                   | Entra ID テナント ID                                                               |
| Foundry Hosted Agent | `BLUEPRINT_CLIENT_ID`         | Blueprint の Application ID（Publish 後に Entra ID で確認）                        |
| Foundry Hosted Agent | `AGENT_IDENTITY_OID`          | Agent Identity の Service Principal OID（`fmi_path` 兼 `client_id`）               |
| Foundry Hosted Agent | `AGENT_USER_OID`              | Agent User の Object ID（`user_fic` の `user_id` パラメータ、Phase 4 以降）        |
| Foundry Hosted Agent | `RESOURCE_API_SCOPE`          | `api://{IDENTITY_ECHO_API_CLIENT_ID}/CallerIdentity.Read`（delegated 用）          |
| Foundry Hosted Agent | `RESOURCE_API_DEFAULT_SCOPE`  | `api://{IDENTITY_ECHO_API_CLIENT_ID}/.default`（app-only `client_credentials` 用） |
| Foundry Hosted Agent | `RESOURCE_API_URL`            | Container Apps にデプロイした Identity Echo API の URL                             |
| Foundry Hosted Agent | `AGENT_USER_UPN`              | `agentuser@contoso.com`（Phase 4 以降、callerType 判定用）                         |
| Frontend SPA         | `VITE_MSAL_CLIENT_ID`         | `demo-client-app` の Client ID                                                     |
| Frontend SPA         | `VITE_MSAL_TENANT_ID`         | Entra ID テナント ID                                                               |
| Frontend SPA         | `VITE_RESOURCE_API_URL`       | Identity Echo API の Container Apps URL                                            |
| Frontend SPA         | `VITE_BACKEND_API_URL`        | Backend API の Container Apps URL                                                  |
| Frontend SPA         | `VITE_BLUEPRINT_APP_ID`       | Blueprint Application の Client ID（Phase 5 以降）                                 |
| Frontend SPA         | `VITE_FOUNDRY_AGENT_ENDPOINT` | Foundry Agent API エンドポイント URL（Phase 5 以降、Interactive 直接呼び出し用）   |

---

## 5. 参考：フローごとの呼び出し主体対比

|                                     | Interactive                                       | Autonomous App                | Autonomous User                       |
| ----------------------------------- | ------------------------------------------------- | ----------------------------- | ------------------------------------- |
| Foundry Agent API の呼び出し主体    | SPA（ユーザーの MSAL token）                      | Backend API（MSI token）      | Backend API（MSI token）              |
| T1 取得に使う credential            | Foundry Project MSI（`DefaultAzureCredential()`） | 同左                          | 同左                                  |
| TR 取得フロー                       | OBO（T1 + Tc → TR）                               | client_credentials（T1 → TR） | user_fic（T1 → T2 → TR）              |
| Identity Echo API が認識する caller | 人間ユーザー（`alice@contoso.com`）               | Agent Identity（OID）         | Agent User（`agentuser@contoso.com`） |
| `callerType`                        | `delegated_human_user`                            | `app_only`                    | `delegated_agent_user`                |
| `tokenKind`                         | `delegated`                                       | `application`                 | `delegated`                           |
