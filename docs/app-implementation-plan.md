# 実装タスク計画書

| 項目               | 内容                                                                                         |
| ------------------ | -------------------------------------------------------------------------------------------- |
| **ドキュメント名** | Entra Agent ID デモアプリ 実装タスク計画書                                                   |
| **バージョン**     | 1.8                                                                                          |
| **作成日**         | 2026-03-27                                                                                   |
| **最終更新日**     | 2026-04-05                                                                                   |
| **ステータス**     | Phase 3 完了（SPA + Autonomous App Flow E2E ローカル＋クラウドデプロイ完了）・Phase 4 準備中 |

---

## 0. 現在のステータスサマリー（2026-04-05 時点）

| Phase   | 名称                          | ステータス | 備考                                                                                                                   |
| ------- | ----------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------- |
| Phase 1 | SPA + Identity Echo API       | ✅ 完了    | ローカル・クラウド両方で動作確認済み                                                                                   |
| Phase 2 | Hosted Agent 最小実装         | ✅ 完了    | Step A-1〜C 全ステップ完了。T1→TR→API の E2E 成功                                                                      |
| Phase 3 | SPA + Autonomous App Flow E2E | ✅ 完了    | ローカル E2E 成功。クラウドデプロイ完了（SWA + CORS + Container Apps 再デプロイ）。クラウド E2E は手動ブラウザ確認待ち |
| Phase 4 | Autonomous User Flow          | ⬜ 未着手  | config.py に変数定義済み（値は未設定）。agent.yaml への変数追加・ツール実装が必要                                      |
| Phase 5 | Interactive Flow              | ⬜ 未着手  | —                                                                                                                      |
| Phase 6 | LLM 整形・UI 最終化           | ⬜ 未着手  | —                                                                                                                      |

**直近の作業履歴（git log）:**

- `9e72b78` fix: Fix CORS error for Identity Echo API — SWA URL を Identity Echo API の CORS に追加
- `655c04d` feat: Add deployment scripts for frontend and backends — `deploy-swa.py` / `deploy-container-apps.py` 自動化スクリプト追加
- `efea47f` fix: Update backend CORS for Static Web App — `FRONTEND_SPA_APP_URL` 環境変数による動的 CORS 設定
- `5e1067b` feat: Add Static Web App resource — Terraform で SWA リソース追加（`main.swa.tf`）
- `1b621ce` fix: Update E2E integration (LLM tool selection) — Agent の instructions 改善
- `3b2c280` feat: Add codes for Phase 3 — AutonomousChatPanel / SSE ストリーミング / タブ UI

**クラウドデプロイ状況:**

| コンポーネント    | URL                                                                                           | ステータス                       |
| ----------------- | --------------------------------------------------------------------------------------------- | -------------------------------- |
| Frontend SPA      | `https://mango-stone-090b84403.4.azurestaticapps.net`                                         | ✅ デプロイ済み（HTTP 200 確認） |
| Backend API       | `https://ca-backend-api-86d21f.gentlesand-f7ed7d5b.swedencentral.azurecontainerapps.io`       | ✅ 稼働中（`/health` → 200）     |
| Identity Echo API | `https://ca-identity-echo-api-86d21f.gentlesand-f7ed7d5b.swedencentral.azurecontainerapps.io` | ✅ 稼働中（`/health` → 200）     |

**デプロイ自動化パイプライン（確立済み）:**

```text
1. terraform apply (src/infra/)          → SWA / Container Apps / ACR / Foundry / Entra ID
2. python src/scripts/sync-infra-env.py  → Terraform output → src/.env に同期
3. python src/scripts/deploy-container-apps.py → ACR ビルド + Container Apps 更新
4. python src/frontend/scripts/deploy-swa.py   → Vite ビルド（クラウド URL 埋め込み）+ SWA デプロイ
```

**次のアクション候補:**

1. **Phase 3 クラウド E2E 確認**: ブラウザで SWA URL にアクセスし、Autonomous App Flow の E2E を確認
2. **Phase 4 実装開始**: Agent User アカウント作成 → `user_fic` トークン交換実装 → `autonomous_user.py` ツール追加

**現在のモデルデプロイメント**: `gpt-5`（`2025-08-07` バージョン、GlobalStandard SKU）

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
│   ├── Dockerfile           # Phase 2 Step A-4 で追加（python:3.11-slim + uvicorn、EXPOSE 8000）✅
│   ├── auth/
│   │   └── token_validator.py
│   └── routes/
│       └── resource.py
├── agent/                   # Phase 2〜: Foundry Hosted Agent（Python）
│   ├── agent.yaml           # azd デプロイ用エージェント定義ファイル
│   ├── README.md
│   ├── entra-agent-id/
│   │   └── set-blueprint-fic.py   # Blueprint FIC 手動登録スクリプト
│   ├── runtime/             # ★ 実際のコードは runtime/ サブディレクトリに配置
│   │   ├── main.py          # Agent 定義 + from_agent_framework(agent).run()
│   │   ├── Dockerfile       # --platform linux/amd64 必須（linux/amd64 以外は起動不可）
│   │   ├── requirements.txt # azure-ai-agentserver-agentframework, azure-identity, httpx
│   │   ├── config.py        # AgentConfig dataclass（環境変数サマリー）
│   │   ├── auth/
│   │   │   └── token_exchange.py    # T1/TR 取得関数（get_t1, exchange_app_token）✅
│   │   └── tools/
│   │       ├── autonomous_app.py    (Phase 2 で追加, @tool) ✅
│   │       ├── debug.py             (check_agent_environment, try_t1_token_acquisition) ✅
│   │       ├── autonomous_user.py   (Phase 4 で追加, @tool)
│   │       └── interactive.py       (Phase 5 で追加, @tool)
│   └── scripts/
│       ├── deploy-agent.py
│       ├── invoke-agent.py
│       └── query*.json
├── backend_api/             # Phase 2C〜: Backend API（FastAPI）✅ 作成済み
│   ├── __init__.py
│   ├── main.py               # Phase 3: CORS ミドルウェア追加 ✅
│   ├── config.py             # 環境変数 + services.ai.azure.com ドメイン変換
│   ├── foundry_client.py     # invoke_agent() + invoke_agent_stream() (SSE)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── routes/
│       └── call_foundry_agent.py  # POST /autonomous/app + /autonomous/app/stream
├── frontend/                # Phase 1〜: SPA（React + TypeScript）
│   ├── scripts/
│   │   └── deploy-swa.py       # SWA デプロイスクリプト（.env.production 生成 → Vite ビルド → swa deploy）✅
│   └── src/
│       ├── authConfig.ts
│       ├── App.tsx               # Phase 3: タブ UI 統合（autonomous-app / identity-echo-debug）✅
│       ├── api/
│       │   ├── identityEchoApi.ts
│       │   └── backendApi.ts        (Phase 3 で追加) ✅ SSE ストリーミング対応
│       ├── components/
│       │   ├── CallerInfo.tsx
│       │   ├── AutonomousChatPanel.tsx (Phase 3 で追加) ✅ チャット形式 UI
│       │   ├── TokenChainSteps.tsx     (Phase 2B+ で追加) ✅
│       │   ├── TokenFlowVisualizer.tsx  (Phase 6 で追加)
│       │   ├── ScenarioComparison.tsx   (Phase 6 で追加)
│       │   └── RawResponse.tsx          (Phase 6 で追加)
│       └── utils/
│           └── extractAgentToolOutput.ts (Phase 3 で追加) ✅ トークンチェーン検証ヘルパー
├── scripts/                 # デプロイ自動化スクリプト ✅
│   ├── sync-infra-env.py       # terraform output → src/.env 同期 ✅
│   └── deploy-container-apps.py # ACR ビルド + Container Apps 更新 ✅
└── infra/                   # Terraform IaC
    ├── main.swa.tf             # Azure Static Web Apps (Free) ✅ Phase 3 で追加
    ├── _variables.swa.tf       # SWA 変数（swa_location）✅
    └── ...                     # その他の .tf ファイル（既存）
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

受け取った JWT の claims から `callerType` を判定する（`ENTRA_AGENT_ID_USER_UPN` 環境変数との照合で Agent User を識別）:

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

| TR の特徴                                     | `callerType`           |
| --------------------------------------------- | ---------------------- |
| `scp` なし、`roles` あり                      | `app_only`             |
| `scp` あり、`upn` = `ENTRA_AGENT_ID_USER_UPN` | `delegated_agent_user` |
| `scp` あり、`upn` ≠ `ENTRA_AGENT_ID_USER_UPN` | `delegated_human_user` |

> `ENTRA_AGENT_ID_USER_UPN` は Identity Echo API の環境変数として設定する（例: `agentuser@contoso.com`）。

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

- [x] `demo-identity-echo-api` App Registration を作成 — ✅ Terraform apply 済み（`resource_api_client_id: 64bf37a9-...`）
  - App ID URI: `api://{Application ID}` を設定 — ✅ `azuread_application_identifier_uri.resource_api`
  - Expose API → Scope: `CallerIdentity.Read`（Delegated）を追加 — ✅ `oauth2_permission_scope`
  - Expose API → App Role: `CallerIdentity.Read.All`（Application、値: `CallerIdentity.Read.All`）を追加 — ✅ `app_role`
- [x] `demo-client-app` App Registration を作成 — ✅ Terraform apply 済み（`client_app_client_id: 4cbb2e7e-...`）
  - Platform: SPA、Redirect URI: `http://localhost:3000`, `http://localhost:5173` を設定 — ✅ `single_page_application`
  - API Permissions: `CallerIdentity.Read`（Delegated）を追加し Admin Consent を実施 — ✅ `required_resource_access` + `delegated_permission_grant`

**(2) Identity Echo API（`src/identity_echo_api/`）**

- [x] `src/identity_echo_api/config.py` — 環境変数（`ENTRA_TENANT_ID`、`ENTRA_RESOURCE_API_CLIENT_ID`） — ✅ `.env` 設定済み
- [x] `src/identity_echo_api/auth/token_validator.py` — JWT 検証ロジック — ✅ 実装済み
  - JWKS エンドポイントから公開鍵取得（`https://login.microsoftonline.com/{tenantId}/discovery/v2.0/keys`）
  - RS256 署名検証、`aud`（= `{RESOURCE_API_CLIENT_ID}`、生の Client ID (GUID)。`requested_access_token_version = 2` のため `api://` URI ではなく GUID が `aud` になる）/ `iss` / `exp` 検証
- [x] `src/identity_echo_api/routes/resource.py` — `GET /api/resource` エンドポイント — ✅ 実装済み
  - `Authorization: Bearer <token>` ヘッダー抽出 → 検証呼び出し
  - JWT クレームから `callerType` / `tokenKind` / `oid` / `upn` / `appId` / `scopes` / `roles` を組み立てて JSON レスポンス
- [x] `src/identity_echo_api/main.py` — FastAPI アプリ、CORS ミドルウェア設定 — ✅ `localhost:3000`, `localhost:5173` 許可

**(3) Frontend SPA（`src/frontend/`）**

- [x] `src/frontend/` に React プロジェクトを作成（Vite + TypeScript） — ✅ 作成済み
- [x] `src/frontend/src/authConfig.ts` — MSAL `PublicClientApplication` 設定（`clientId`、`authority`、`redirectUri`、スコープ） — ✅ `.env` から読み込み
- [x] `src/frontend/src/App.tsx` — ログイン / ログアウトボタン、認証済み UI の分岐 — ✅ `AuthenticatedTemplate` / `UnauthenticatedTemplate`
- [x] `src/frontend/src/api/identityEchoApi.ts` — `getCallerInfo(accessToken: string)` 関数 — ✅ `Authorization: Bearer` 付きで `GET /api/resource`
- [x] `src/frontend/src/components/CallerInfo.tsx` — レスポンス JSON を整形表示するコンポーネント — ✅ テーブル形式で表示

**(4) ローカル動作確認**

- [x] Identity Echo API 起動 → トークンなし `GET /api/resource` が HTTP 401 を返すことを確認 — ✅ `poe api` で起動、`curl` で 401 確認済み
- [x] SPA でログイン → `CallerIdentity.Read` スコープのトークン取得を確認 — ⬜ ブラウザでの手動確認が必要
- [x] `GET /api/resource` に Bearer トークン付与 → `callerType: "delegated_human_user"` が返ることを確認 — ⬜ ブラウザでの手動確認が必要

#### 切り分けポイント

| 問題                                      | 原因の候補                                                                                                                                     |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| MSAL のログインが動かない                 | リダイレクト URI の不一致、テナント ID の誤り                                                                                                  |
| トークンが Identity Echo API に拒否される | `aud` の不一致（`requested_access_token_version = 2` では `aud` は生の Client ID (GUID) であり `api://` URI ではない点に注意）、`iss` の不一致 |
| CORS エラー                               | Identity Echo API の CORS 設定漏れ                                                                                                             |

---

### Phase 2: Foundry Hosted Agent 最小実装（Autonomous App Flow）

#### 目的

Foundry Hosted Agent のコンテナ内で **T1 取得 → TR 取得（client_credentials）→ Identity Echo API 呼び出し** を動作させる。

Entra Agent ID の設定（Blueprint / Agent Identity / Federated Credential）が正しいことを確立する最初のフェーズ。**SPA との統合はこのフェーズでは行わない**。

#### 追加するコンポーネント

| コンポーネント           | 役割                                            | 実装                                             |
| ------------------------ | ----------------------------------------------- | ------------------------------------------------ |
| **Foundry Hosted Agent** | T1 取得、TR 取得、Identity Echo API 呼び出し    | Python、Microsoft Agent Framework or custom code |
| **Backend API**（最小）  | Foundry Hosted Agent を呼び出すエントリポイント | Python FastAPI、専用 UAMI（`uami-ca-foundry-*`） |

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
from agent_framework import Agent                                   # v1.0.0b17: ChatAgent → Agent
from agent_framework_azure_ai import AzureAIAgentClient             # v1.0.0b17: agent_framework.azure → agent_framework_azure_ai
from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity import DefaultAzureCredential
from tools.autonomous_app import call_resource_api_autonomous_app

agent = Agent(
    client=AzureAIAgentClient(                                      # v1.0.0b17: chat_client → client
        project_endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT"),
        model_deployment_name=os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1"),
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
name: demo-entraagtid-agent
image: ${FOUNDRY_AGENT_ACR_LOGIN_SERVER}/demo-agent:latest
cpu: "1"
memory: 2Gi
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

**`config.py`**（環境変数サマリー）:

```python
import os
from dataclasses import dataclass

@dataclass
class AgentConfig:
    tenant_id: str            = os.getenv("ENTRA_TENANT_ID", "")
    project_endpoint: str     = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
    model_deployment_name: str = os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "")
    blueprint_client_id: str  = os.getenv("ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID", "")  # Blueprint Application ID
    agent_identity_oid: str   = os.getenv("ENTRA_AGENT_IDENTITY_CLIENT_ID", "")   # fmi_path 兼 client_id
    agent_user_oid: str       = os.getenv("AGENT_USER_OID", "")       # user_fic の user_id
    agent_user_upn: str       = os.getenv("ENTRA_AGENT_ID_USER_UPN", "")       # callerType 判定用
    resource_api_url: str           = os.getenv("RESOURCE_API_URL", "")
    resource_api_scope: str         = os.getenv("ENTRA_RESOURCE_API_SCOPE", "")           # delegated 用: api://{id}/CallerIdentity.Read
    resource_api_default_scope: str = os.getenv("ENTRA_RESOURCE_API_DEFAULT_SCOPE", "")   # app-only 用: api://{id}/.default

config = AgentConfig()
```

**Backend API（最小実装）**

```text
POST /api/demo/autonomous/app
  → Foundry Hosted Agent を呼び出し、レスポンスを返す
  （この段階ではフロントエンドとの統合なし、curl や REST クライアントで直接テスト）
```

#### Azure / Entra ID 設定（新規）

| 設定項目                      | 内容                                                                                                                    |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Agent Identity Blueprint      | Foundry Project 作成時に共有 Blueprint が自動プロビジョニング。Publish 時に個別 Blueprint が別途作成される              |
| Agent Identity                | 同上（共有 Agent Identity → Publish 後は個別 Agent Identity）                                                           |
| Capability Host               | Hosted Agent 有効化に必須（`Microsoft.CognitiveServices/accounts/capabilityHosts`、Terraform `azapi_resource` で作成）  |
| Azure Container Registry      | Hosted Agent コンテナイメージの格納先（Terraform `azurerm_container_registry` で作成）                                  |
| ACR RBAC                      | Foundry Project MI に `Container Registry Repository Reader` ロールを付与（Terraform `azurerm_role_assignment` で設定） |
| Identity Echo API の App Role | Agent Identity に Application Permission を付与                                                                         |
| Backend API の専用 UAMI       | Foundry Account スコープで Cognitive Services User ロールを付与                                                         |

> **重要**: Agent Identity Blueprint・Agent Identity は Foundry が**プロジェクト作成時に共有 Identity を自動プロビジョニング**する。Publish 時にはエージェント固有の Identity が別途作成され、RBAC の再設定が必要。
>
> Hosted Agent に必要な追加インフラ（ACR、Capability Host、ACR RBAC）は `src/infra/` の Terraform IaC で管理する。手動での Azure Portal 操作は最小限に抑える。

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

**ランタイム環境の実態（v5 環境変数ダンプより）:**

Hosted Agent のコンテナは **Azure Container Apps** 上で動作する。ランタイムが注入する主要な環境変数:

| 環境変数            | 値                          | 説明                                                                                                                    |
| ------------------- | --------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `AZURE_CLIENT_ID`   | (自動注入)                  | Foundry Project の System-Assigned MI の Client ID。`DefaultAzureCredential()` がこの値を検出して MI トークンを取得する |
| `IDENTITY_ENDPOINT` | Container Apps MI endpoint  | Managed Identity トークン取得エンドポイント                                                                             |
| `MSI_ENDPOINT`      | Container Apps MSI endpoint | 同上（レガシー形式）                                                                                                    |

`DefaultAzureCredential()` は `AZURE_CLIENT_ID` を検出し、自動的に **Project MI** のトークンを返す。Agent Identity のトークンは返さない。

**2 つの Identity システムの確定:**

| Identity           | Application ID (appid)                | Object ID (oid)                    | 用途                                                               |
| ------------------ | ------------------------------------- | ---------------------------------- | ------------------------------------------------------------------ |
| **Project MI**     | Foundry Project の System-Assigned MI | (MI の Service Principal OID)      | `DefaultAzureCredential()` が返す。ACR Pull、Azure Management など |
| **Agent Identity** | Blueprint の Application (Client) ID  | Blueprint の Service Principal OID | T1 トークンの subject。Identity Echo API へのアクセス主体          |

**T1 トークン取得の実証:**

**試行 1: 既定の FIC のみの状態（手動 FIC 登録前）**

```text
Step 1: Project MI → api://AzureADTokenExchange トークン取得
  結果: ✅ 成功
  aud: {api://AzureADTokenExchange の Resource ID}
  sub/oid: {Project MI の Object ID}
  idtyp: app

Step 2: MI トークンを client_assertion として Blueprint の T1 取得
  結果: ❌ 失敗
  error: invalid_client
  error_description: AADSTS700213: No matching federated identity record
    found for presented assertion subject '{Project MI の Object ID}'.
  → 既定 FIC の subject は Azure ML 内部 FMI パスであり、
    Project MI の oid とは一致しないためエラーとなる
```

**試行 2: Blueprint に Project MI 用の FIC を手動登録した後（v8 での最終結果）**

```text
Step 1: Project MI → api://AzureADTokenExchange トークン取得
  結果: ✅ 成功
  aud: {api://AzureADTokenExchange の Resource ID}
  sub/oid: {Project MI の Object ID}
  idtyp: app

Step 2: MI トークンを client_assertion として Blueprint の T1 取得
  結果: ✅ 成功 (HTTP 200)
  token_type: Bearer
  expires_in: 3599
  T1 claims:
    aud: {api://AzureADTokenExchange の Resource ID}
    iss: https://login.microsoftonline.com/{tenantId}/v2.0
    sub: /eid1/c/pub/t/{tenantId_b64}/a/{appId_b64}/{Agent Identity ID}
    oid: {Blueprint の Service Principal Object ID}
    idtyp: app
```

**FIC（Federated Identity Credential）に関する重要な発見:**

Foundry が Blueprint に自動プロビジョニングする FIC は **1 つのみ**であり、その subject は Azure Machine Learning の内部 FMI パス（`/eid1/c/pub/t/{tenantId}/a/{AML_AppID}/AzureAI/FMI`）である。この FIC は Agent Service の内部インフラ（MCP ツール認証等）のために Azure ML の First-Party App が使用するものであり、**Hosted Agent コンテナ内のユーザーコードからは利用できない**。

`DefaultAzureCredential()` が返す Project MI のトークンの `oid` は、この既定 FIC の subject とは一致しないため、そのままでは T1 トークンの取得に失敗する（`AADSTS700213: No matching federated identity record found`）。

```text
既定 FIC (Foundry 自動プロビジョニング):
  subject: /eid1/c/pub/t/{tenantId_b64}/a/{AML_AppID_b64}/AzureAI/FMI
  → Azure Machine Learning First-Party App の内部 FMI 専用
  → Hosted Agent 内のユーザーコードからは使用不可
```

> **このデモでの対応**: 本デモが目標とする「Hosted Agent 内のコードから Agent Identity として Identity Echo API にアクセスする」シナリオを実現するため、**Blueprint に Project MI 用の FIC を手動で登録**した。これは Foundry の既定動作の範囲外であり、検証の過程で判明した要件である。
>
> ```text
> 手動登録した FIC:
>   subject:  {Project MI の Object ID}  ← DefaultAzureCredential() が返すトークンの oid と一致させる
>   issuer:   https://login.microsoftonline.com/{tenantId}/v2.0
>   audience: api://AzureADTokenExchange
> ```
>
> この手動 FIC 登録により、Project MI のトークンを `client_assertion` として Blueprint に提示し、T1（Agent Identity として振る舞うトークン）を取得できるようになった。

**Agent 呼び出し方法の確定:**

Hosted Agent の呼び出しは OpenAI Responses API + `agent_reference` パラメータで行う:

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

project = AIProjectClient(
    endpoint="https://{account}.services.ai.azure.com/api/projects/{project}",
    credential=DefaultAzureCredential(),
    allow_preview=True,
)
openai = project.get_openai_client()
agent = project.agents.get(agent_name="demo-entra-agent-id")

response = openai.responses.create(
    input=[{"role": "user", "content": "..."}],
    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}}
)
```

> **ポイント**: `model` パラメータではなく `extra_body.agent_reference` で Hosted Agent を指定する。`endpoint` は `services.ai.azure.com` ドメインを使用する。

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
- [x] SPA でログイン → Identity Echo API 呼び出し → `callerType: "delegated_human_user"` が返ることを確認 — ✅ 確認済み
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
- **SPA（Phase 1）からクラウド API を呼び出し、`callerType: "delegated_human_user"` が返ることを確認済み**（Identity Echo API のトークン検証が正常に動作する証拠）
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
- [x] Identity Echo API から `callerType: "app_only"` と Agent Identity の OID が返ることを確認 — ✅ 全 3 ステップ成功を確認

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
        "callerType": "app_only",
        "oid": "6fac9afc-...",
        "roles": ["CallerIdentity.Read.All"]
      }
    }
  }
}
```

> **確認事項**: TR の `aud` が Identity Echo API の App ID（`52d603ac-...`）と一致、`sub`/`oid` が Agent Identity OID（`6fac9afc-...`）と一致、`roles` に `CallerIdentity.Read.All` が含まれる。Identity Echo API は `callerType: "app_only"` を正しく判定。

**切り分けポイント:**

| 問題                                   | 原因の候補                                                                      |
| -------------------------------------- | ------------------------------------------------------------------------------- |
| T1 取得が失敗する                      | Federated Credential の設定誤り、MSI の権限不足、Blueprint Client ID 誤り       |
| TR 取得が失敗する                      | Agent Identity の Application Permission 未付与、scope 形式（`/.default` 必須） |
| Identity Echo API がトークンを拒否する | `aud` の不一致（Identity Echo API の App ID と不一致）                          |
| `callerType` が `app_only` にならない  | TR 取得フローが `client_credentials` になっていない                             |

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
- [x] `POST /api/demo/autonomous/app` に curl → `callerType: "app_only"` と Agent Identity OID が返ることを確認 — ✅ E2E 成功（`oid: 6fac9afc-...`, `roles: ["CallerIdentity.Read.All"]`）
- [x] `POST /api/demo/autonomous/app/stream` に curl → SSE イベントがストリーミングで返ることを確認 — ✅ `response.created` → `response.output_text.delta` (逐次) → `response.completed` の一連の SSE イベントを確認

**切り分けポイント:**

| 問題                                                    | 原因の候補                                                                 |
| ------------------------------------------------------- | -------------------------------------------------------------------------- |
| Backend API から Foundry Agent API の呼び出しが失敗する | Backend API の MSI に `Cognitive Services User` ロール未付与               |
| Foundry SDK のバージョンエラー                          | `azure-ai-projects >= 2.0.0` 未インストール                                |
| レスポンスがタイムアウトする                            | Agent deployment が停止状態、min_replicas = 0 でコールドスタート           |
| SSE イベントがバッファリングされて一括で返る            | リバースプロキシのバッファリング設定（`X-Accel-Buffering: no` で対応済み） |

#### SDK・MSI 対応（確認済み事項）

公式ドキュメント ([What are hosted agents?](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)) により以下が確認済みのため、実装前の調査は不要：

- **`azure-identity` による MSI 認証は可能**。Foundry Hosted Agent のコンテナには System-Assigned MSI が自動付与されており、`DefaultAzureCredential()` で透過的にトークンを取得できる。Backend API 側は専用 UAMI（`uami-ca-foundry-*`）を作成し、`AZURE_CLIENT_ID` 環境変数で `DefaultAzureCredential()` に選択させる設計を採用した。
- **SDK は `azure-ai-projects 2.x`（Responses API / Agents v2）**。旧 Assistants API v1 の Thread/Run/Message から Conversation/Response/Item に用語が変更されている。詳細は [azure-ai-projects SDK ドキュメント](https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/sdk-overview) を参照。

---

### Phase 3: SPA + Autonomous App Flow 統合（E2E）

#### 目的

Phase 1 の SPA と Phase 2 の Backend API + Foundry Hosted Agent を接続し、**Autonomous App Flow のエンドツーエンドを完成させる**。

#### 追加・変更するコンポーネント

| コンポーネント   | 変更内容                                | 実装結果 |
| ---------------- | --------------------------------------- | -------- |
| **Frontend SPA** | Autonomous チャット UI と結果表示を追加 | ✅ 完了  |
| **Backend API**  | CORS 設定、エラーハンドリングを追加     | ✅ 完了  |

#### 実装内容

**Frontend SPA 変更点（実装済み）**

- タブベースの UI（`autonomous-app` / `identity-echo-debug`）を追加。Autonomous App タブはログイン不要
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
- [x] 画面に `callerType: "app_only"`、Agent Identity OID が表示されることを確認 — ✅ ツール出力の `step3_call_resource_api.body.caller` に `callerType: "app_only"`, `oid: "6fac9afc-..."`, `roles: ["CallerIdentity.Read.All"]` が表示。トークンチェーン成功バッジ（「取得済み」）も表示

#### 完成した E2E フローの詳細

```text
👤 ユーザー（ログイン不要）
  → [チャット送信] → SPA (AutonomousChatPanel)
  → POST /api/demo/autonomous/app/stream → Backend API (MSI token, SSE)
  → Foundry Hosted Agent
      → call_resource_api_autonomous_app() Function Tool
          → T1 取得 (Project MSI → Blueprint FIC)
          → TR 取得 (client_credentials, scope=api://{id}/.default)
          → GET /api/resource (Bearer TR) → Identity Echo API
  ← SSE events: response.created → function_call → function_call_output
     → output_text.delta (逐次) → response.completed
  ← SPA: テキストデルタをリアルタイム表示 + ツール出力を JSON で折りたたみ表示
  ← トークンチェーン結果: 成功バッジ + CallerInfo 表示
```

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

**(2) Hosted Agent の変更（`src/agent/runtime/`）**

- [ ] `src/agent/runtime/auth/token_exchange.py` に `get_t2(t1)` と `exchange_agent_user_token(t1, t2, user_id)` を追加（`grant_type=user_fic` で Agent User TR を取得）
- [ ] `src/agent/runtime/tools/autonomous_user.py` を新規作成し `call_resource_api_autonomous_user()` Function Tool を実装（`@tool` デコレータ）
- [x] `src/agent/runtime/config.py` に `ENTRA_AGENT_ID_USER_UPN` 環境変数を追加 — ✅ Phase 2 で `agent_user_oid` / `agent_user_upn` として定義済み（optional、Phase 4 で値を設定）
- [ ] `src/agent/agent.yaml` の `environment_variables` に `AGENT_USER_OID` と `ENTRA_AGENT_ID_USER_UPN` を追加（※ 変数名は定義済みだが、`agent.yaml` には未追加。デプロイ時に渡す必要あり）
- [ ] `src/agent/runtime/main.py` に新 Function Tool を登録

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

**(2) Hosted Agent の変更（`src/agent/runtime/`）**

- [ ] `src/agent/runtime/auth/token_exchange.py` に `exchange_interactive_obo(t1, tc)` を追加（T1 + Tc → TR、OBO grant type、sub = 人間ユーザー）
- [ ] `src/agent/runtime/tools/interactive.py` を新規作成し `call_resource_api_interactive(tc: str)` Function Tool を実装（`@tool` デコレータ）
- [ ] `src/agent/runtime/main.py` に新 Function Tool を登録

**(3) Frontend SPA の変更（`src/frontend/`）**

- [ ] `src/frontend/src/authConfig.ts` に Blueprint スコープ（`api://{BlueprintId}/access_agent`）を追加
- [ ] `src/frontend/src/api/backendApi.ts` に `runInteractive()` 関数を追加
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

**(1) Foundry Hosted Agent の更新（`src/agent/runtime/`）**

- [ ] `src/agent/runtime/main.py` の system prompt を Phase 6 の内容に更新（3 シナリオ共通の説明テンプレート）

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

| フェーズ | App Registration / Azure リソース                                                                                                                           | 用途                                                              |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Phase 1  | `demo-client-app`（SPA）、`demo-identity-echo-api`（API）                                                                                                   | MSAL 認証、Bearer 検証                                            |
| Phase 2  | Foundry Project（→ Blueprint/Agent Identity を自動生成）、Backend API（Managed Identity）、**Container Apps Environment + Identity Echo API Container App** | Hosted Agent 実行環境、T1/TR 取得、Identity Echo API クラウド公開 |
| Phase 3  | **Azure Static Web Apps**（SPA デプロイ先）、Backend API / Identity Echo API の動的 CORS 設定、デプロイ自動化スクリプト                                     | SWA デプロイ、CORS 動的設定                                       |
| Phase 4  | Agent User アカウント（`agentuser@contoso.com`）                                                                                                            | Autonomous User Flow                                              |
| Phase 5  | `demo-client-app` の API アクセス設定に Blueprint スコープを追加                                                                                            | Interactive Flow Tc 取得                                          |
| Phase 6  | 追加なし                                                                                                                                                    | -                                                                 |

### Foundry の自動プロビジョニングにより手動設定不要なもの

- Agent Identity Blueprint
- Agent Identity（Service Principal）
- Federated Credential（Foundry Project MSI ↔ Blueprint）
- Hosted Agent の System-Assigned MSI（未公開時）／Dedicated Agent Identity（公開後）

---

## 4. Azure デプロイ構成

### 4.1 コンポーネント別デプロイ先

| コンポーネント        | Azure サービス            | SKU         | 選定理由                                                                                                                 |
| --------------------- | ------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------ |
| **Frontend SPA**      | Azure Static Web Apps     | Free        | 静的ファイル配信・CDN 内蔵・HTTPS URL 自動発行・GitHub Actions CI/CD 標準統合                                            |
| **Identity Echo API** | Azure Container Apps      | Consumption | コンテナ化 FastAPI に適合・スケールゼロ対応・将来的に Internal Ingress 化可能                                            |
| **Backend API**       | Azure Container Apps      | Consumption | **専用 UAMI が必須**（Foundry Agent API の MSI 呼び出しに `AZURE_CLIENT_ID` で選択）・Identity Echo API と同一運用モデル |
| **Foundry Agent**     | Microsoft Foundry Project | Standard    | Hosted Agent のコンテナ実行環境・MSI 自動付与・Blueprint/Agent Identity 自動生成                                         |

### 4.2 フェーズごとのデプロイタスク

#### Phase 1 デプロイ

- [x] Azure Static Web Apps リソースを作成し、SPA の Redirect URI（HTTPS）を Entra ID `demo-client-app` に追加登録 — ✅ `main.swa.tf`（Free tier、`westeurope`）+ `main.adapp.client-spa.tf`（SWA URL を `redirect_uris` に自動追加）
- [x] SPA を Static Web Apps にデプロイ（`npm run build` → Azure CLI or GitHub Actions） — ✅ `src/frontend/scripts/deploy-swa.py` で自動化（`.env.production` 生成 → Vite ビルド → `swa deploy`）
- [x] Identity Echo API の CORS 許可オリジンに Static Web Apps の URL を設定 — ✅ `FRONTEND_SPA_APP_URL` 環境変数で動的 CORS（`src/identity_echo_api/main.py`）+ Terraform で Container App に注入
- [ ] デプロイ後 E2E 確認: SPA ログイン → Identity Echo API 呼び出し → `callerType: "delegated_human_user"` を確認 — ⬜ ブラウザでの手動確認待ち

> **注**: Identity Echo API の Dockerfile 作成・ Container Apps Environment 作成・デプロイは Phase 2 Step A-4 に前倒しした。Phase 1 デプロイでは SPA のデプロイと CORS 設定のみを行う。
> **SWA デプロイ URL**: `https://mango-stone-090b84403.4.azurestaticapps.net`

#### Phase 2 デプロイ

**Step A-4: Identity Echo API クラウドデプロイ**

- [x] Identity Echo API の `Dockerfile` を作成（`src/identity_echo_api/Dockerfile`） — ✅ 作成済み
- [x] Terraform で Container Apps Environment + Identity Echo API Container App を作成 — ✅ `main.containerapp.tf` + `main.containerapp.apps.tf` + `terraform.tfvars` で定義・apply 済み
- [x] Identity Echo API イメージを既存 ACR に push — ✅ `null_resource.acr_build["identity-echo-api"]` で自動ビルド・push
- [x] デプロイ後確認: `curl https://{fqdn}/health` → `{"status": "ok"}`、`curl https://{fqdn}/api/resource` → 401 — ✅ Step A-4 段階 1 で確認済み

**Step B 以降:**

- [x] Hosted Agent の `RESOURCE_API_URL` を Container App の FQDN に更新し Agent version を再作成 — ✅ Step A-4 段階 3 で確認済み
- [x] Foundry Agent API 経由で `call_resource_api_autonomous_app` の E2E テスト — ✅ Step B で確認済み（`callerType: "app_only"`, `oid: 6fac9afc-...`）

**Step C: Backend API**

- [x] Backend API のコーディング（`src/backend_api/`） — ✅ config.py, foundry_client.py, routes/demo.py, main.py, requirements.txt 作成済み
- [x] SSE ストリーミング対応（`POST /api/demo/autonomous/app/stream`） — ✅ OpenAI Responses API イベントを SSE フレームとして中継
- [x] Backend API の `Dockerfile` を作成 — ✅ `python:3.11-slim` + `uvicorn`
- [x] ローカル E2E 確認: 一括レスポンス + SSE ストリーミングの両方で `callerType: "app_only"` を確認 — ✅ 検証済み
- [x] Backend API を同一 Container Apps 環境にデプロイ（`terraform apply`） — ✅ apply 済み
- [x] Backend API の Container App に**専用 UAMI（`uami-ca-foundry-*`）をアタッチ** — ✅ `AZURE_CLIENT_ID` env で `DefaultAzureCredential()` が選択
- [x] Backend API の専用 UAMI に Foundry **Account** スコープで `Cognitive Services User` ロールを付与 — ✅ apply 済み
- [x] デプロイ後確認: `GET /health` → `{"status": "ok"}` — ✅ 確認済み（コールドスタート約 10 秒）
- [x] デプロイ後確認: `POST /api/demo/autonomous/app` に curl → `callerType: "app_only"` を確認 — ✅ E2E 成功（`oid: 6fac9afc-...`, `roles: ["CallerIdentity.Read.All"]`）
- [x] デプロイ後確認: `POST /api/demo/autonomous/app/stream` に curl → SSE イベントがストリーミングで返ることを確認 — ✅ `response.created` → `function_call` → `function_call_output` → `output_text.delta` (逐次) → `response.completed`

#### Phase 3 デプロイ

- [x] Backend API の CORS 許可オリジンに `http://localhost:5173`, `http://localhost:4173` を追加 — ✅ `src/backend_api/main.py` に `CORSMiddleware` 追加済み
- [x] SPA に Autonomous App チャット UI を追加 — ✅ `AutonomousChatPanel.tsx` + `backendApi.ts`（SSE ストリーミング）+ `extractAgentToolOutput.ts`（ヘルパー）、タブ UI（`autonomous-app` / `identity-echo-debug`）
- [x] ローカル E2E 確認: SPA チャット UI → Backend API → Foundry Agent → Identity Echo API の順に動作を確認 — ✅ `http://localhost:5173` からの SSE ストリーミング E2E 成功
- [x] クラウドデプロイ: Backend API の CORS 許可オリジンに Static Web Apps の URL を追加して再デプロイ — ✅ `FRONTEND_SPA_APP_URL` 環境変数による動的 CORS 設定を実装。Terraform で SWA URL を Container App に自動注入。`deploy-container-apps.py` で再デプロイ済み
- [x] クラウドデプロイ: Identity Echo API の CORS 許可オリジンにも SWA URL を追加して再デプロイ — ✅ 同じ `FRONTEND_SPA_APP_URL` パターンで実装（`9e72b78` で修正）
- [x] クラウドデプロイ: SPA を Static Web Apps にデプロイ — ✅ `deploy-swa.py` でクラウド API URL を `.env.production` にベイク → SWA デプロイ（`https://mango-stone-090b84403.4.azurestaticapps.net`）
- [ ] クラウド E2E 確認: デプロイ済み SPA → Backend API → Foundry Agent → Identity Echo API の E2E を確認 — ⬜ ブラウザでの手動確認待ち

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

| コンポーネント       | 変数名                                     | 設定値の例 / 取得元                                                                |
| -------------------- | ------------------------------------------ | ---------------------------------------------------------------------------------- |
| Identity Echo API    | `ENTRA_TENANT_ID`                          | Entra ID テナント ID                                                               |
| Identity Echo API    | `ENTRA_RESOURCE_API_CLIENT_ID`             | `demo-identity-echo-api` App Registration の Client ID                             |
| Identity Echo API    | `ENTRA_AGENT_ID_USER_UPN`                  | `agentuser@contoso.com`（callerType 判定用、Phase 4 以降）                         |
| Identity Echo API    | `FRONTEND_SPA_APP_URL`                     | SWA の URL（動的 CORS 用、Terraform output から自動注入）                          |
| Backend API          | `FOUNDRY_PROJECT_ENDPOINT`                 | Microsoft Foundry のプロジェクトエンドポイント URL                                 |
| Backend API          | `ENTRA_TENANT_ID`                          | Entra ID テナント ID                                                               |
| Backend API          | `FRONTEND_SPA_APP_URL`                     | SWA の URL（動的 CORS 用、Terraform output から自動注入）                          |
| Backend API          | `AZURE_CLIENT_ID`                          | Backend API 専用 UAMI の Client ID（`DefaultAzureCredential()` が選択）            |
| Foundry Hosted Agent | `ENTRA_TENANT_ID`                          | Entra ID テナント ID                                                               |
| Foundry Hosted Agent | `FOUNDRY_PROJECT_ENDPOINT`                 | Foundry Project エンドポイント URL                                                 |
| Foundry Hosted Agent | `FOUNDRY_MODEL_DEPLOYMENT_NAME`            | モデルデプロイメント名（例: `gpt-5`）                                              |
| Foundry Hosted Agent | `ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID` | Blueprint の Application ID                                                        |
| Foundry Hosted Agent | `ENTRA_AGENT_IDENTITY_CLIENT_ID`           | Agent Identity の Service Principal OID（`fmi_path` 兼 `client_id`）               |
| Foundry Hosted Agent | `AGENT_USER_OID`                           | Agent User の Object ID（`user_fic` の `user_id` パラメータ、Phase 4 以降）        |
| Foundry Hosted Agent | `ENTRA_RESOURCE_API_SCOPE`                 | `api://{id}/CallerIdentity.Read`（delegated 用）                                   |
| Foundry Hosted Agent | `ENTRA_RESOURCE_API_DEFAULT_SCOPE`         | `api://{id}/.default`（app-only `client_credentials` 用）                          |
| Foundry Hosted Agent | `RESOURCE_API_URL`                         | Container Apps にデプロイした Identity Echo API の URL                             |
| Foundry Hosted Agent | `ENTRA_RESOURCE_API_CLIENT_ID`             | `demo-identity-echo-api` の Client ID（optional）                                  |
| Foundry Hosted Agent | `ENTRA_AGENT_ID_USER_UPN`                  | `agentuser@contoso.com`（Phase 4 以降、callerType 判定用）                         |
| Frontend SPA         | `BACKEND_API_URL`                          | Backend API の URL（ローカル: `http://localhost:8000`、Azure: Container Apps URL） |
| Frontend SPA         | `ENTRA_SPA_APP_CLIENT_ID`                  | `demo-client-app` の Client ID                                                     |
| Frontend SPA         | `ENTRA_TENANT_ID`                          | Entra ID テナント ID                                                               |
| Frontend SPA         | `RESOURCE_API_URL`                         | Identity Echo API の Container Apps URL                                            |
| Frontend SPA         | `ENTRA_RESOURCE_API_SCOPE`                 | `api://{id}/CallerIdentity.Read`（Identity Echo API スコープ）                     |
| Frontend SPA         | `ENTRA_RESOURCE_API_CLIENT_ID`             | `demo-identity-echo-api` の Client ID                                              |

> **Vite 環境変数の注記**: SPA は `VITE_` プレフィックスではなく、`vite.config.ts` の `envPrefix: ['ENTRA_', 'RESOURCE_API_', 'FOUNDRY_', 'BACKEND_']` で定義されたプレフィックスを使用する。`.env` ファイルは `src/` ディレクトリに配置し、全コンポーネントで共有する（`envDir: '../'`）。Phase 3 で `BACKEND_API_URL` を追加済み。Phase 5 で追加予定の Frontend 変数（Blueprint App ID、Foundry Agent Endpoint）は実装時に追記する。
>
> **クラウドデプロイ時の変数注入**: `deploy-swa.py` が `src/.env` のローカル URL を Terraform output のクラウド URL に置換した `.env.production` を生成し、Vite ビルド時に埋め込む。Container Apps の `FRONTEND_SPA_APP_URL` は Terraform が SWA リソースの `default_host_name` から自動算出して注入する。

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
