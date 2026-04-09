# 実装計画書

| 項目               | 内容                                                                                                       |
| ------------------ | ---------------------------------------------------------------------------------------------------------- |
| **ドキュメント名** | Entra Agent ID デモアプリ 実装計画書                                                                       |
| **バージョン**     | 1.9                                                                                                        |
| **作成日**         | 2026-03-27                                                                                                 |
| **最終更新日**     | 2026-04-09                                                                                                 |
| **ステータス**     | Phase 5 完了（Interactive OBO Flow E2E 完了）・Phase 4 コード実装済み（Entra ID 設定待ち）・Phase 6 未着手 |

---

## 0. 現在のステータスサマリー（2026-04-09 時点）

| Phase   | 名称                                | ステータス | 備考                                                                                                                   |
| ------- | ----------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------- |
| Phase 1 | SPA + Identity Echo API             | ✅ 完了    | ローカル・クラウド両方で動作確認済み                                                                                   |
| Phase 2 | Hosted Agent 最小実装               | ✅ 完了    | Step A-1〜C 全ステップ完了。T1→TR→API の E2E 成功                                                                      |
| Phase 3 | SPA + Autonomous Agent App Flow E2E | ✅ 完了    | ローカル E2E 成功。クラウドデプロイ完了（SWA + CORS + Container Apps 再デプロイ）。クラウド E2E は手動ブラウザ確認待ち |
| Phase 4 | Autonomous Agent User Flow          | ✅ 完了    | Agent Runtime コード実装 + Agent User 作成・consent 付与完了                                                           |
| Phase 5 | Interactive Flow（OBO）             | ✅ 完了    | CLI E2E テスト成功。Frontend（InteractiveOboPanel）+ Agent Runtime（OBO ツール）+ SPA デプロイ完了                     |
| Phase 6 | LLM 整形・UI 最終化                 | ⬜ 未着手  | —                                                                                                                      |

**直近の作業履歴（git log）:**

- `be52b22` fix: Fix script error
- `aa69bc0` feat: Add Interactive Agent OBO scenario — InteractiveOboPanel + foundryAgentApi.ts（Phase 5 Frontend）
- `4469b67` feat: Add call_resource_api_interactive_obo tool and related codes — OBO ツール + request_context + metadata チャンキング（Phase 5 Agent）
- `4cf82f9` feat: Add call_resource_api_autonomous_user tool — autonomous_user.py + exchange_user_t2/exchange_user_token（Phase 4 Agent）
- `0aab8d3` fix: Update outputs from Identity Echo API — `callerType` 廃止 → `tokenKind` に統一
- `27d6678` fix: Update frontend codes for Agent Tools selection — AutonomousChatPanel にツール選択 UI 追加
- `9e72b78` fix: Fix CORS error for Identity Echo API — SWA URL を Identity Echo API の CORS に追加
- `655c04d` feat: Add deployment scripts for frontend and backends — `deploy-swa.py` / `deploy-container-apps.py` 自動化スクリプト追加

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

1. ~~**Phase 4 完了**~~: ✅ Agent User 作成・consent 付与・E2E テスト完了
2. **Phase 6 実装開始**: System Prompt 充実 → トークンフロー可視化 UI → 比較モード

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

| #           | フェーズ                                           | 新たに追加する概念                                                                 | 主な検証ポイント                                                |
| ----------- | -------------------------------------------------- | ---------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| **Phase 1** | SPA + Identity Echo API                            | MSAL Auth Code Flow + PKCE、Bearer 認証                                            | CORS、App Registration、scope/audience                          |
| **Phase 2** | Hosted Agent 最小実装（Autonomous Agent App Flow） | Foundry Hosted Agent、T1 取得、client_credentials、Backend API（テスト用最小構成） | Blueprint/Agent Identity/Federated Credential、T1 ロジック      |
| **Phase 3** | SPA + Autonomous Agent App Flow 統合（E2E）        | Backend API、Managed Identity、SPA トリガー                                        | エンドツーエンドフロー                                          |
| **Phase 4** | Autonomous Agent User Flow 追加                    | Agent User、user_fic                                                               | Agent User 設定、delegated 権限                                 |
| **Phase 5** | Interactive Flow                                   | MSAL Tc 取得（Blueprint scope）、OBO（T1+Tc→TR）                                   | OBO 交換、Tc の audience、CORS（ブラウザ→Foundry 直接呼び出し） |
| **Phase 6** | LLM 整形・UI 最終化                                | System Prompt 充実、フロー可視化 UI                                                | LLM 品質、UX                                                    |

### 1.4 フェーズ間の依存関係

```text
Phase 1: SPA + Identity Echo API
    │
    ├──→ Phase 2: Hosted Agent 最小実装 (Autonomous Agent App)
    │              │
    │              └──→ Phase 3: SPA 統合 (Autonomous Agent App E2E)
    │                              │
    │                              └──→ Phase 4: Autonomous Agent User Flow
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
│   │   ├── request_context.py  # per-request Tc トークンコンテキスト（OBO 用）✅
│   │   ├── auth/
│   │   │   └── token_exchange.py    # T1/TR 取得関数（get_t1, exchange_app_token, exchange_user_t2, exchange_user_token, exchange_interactive_obo）✅
│   │   └── tools/
│   │       ├── autonomous_app.py    (Phase 2 で追加, @tool) ✅
│   │       ├── debug.py             (check_agent_environment, try_t1_token_acquisition) ✅
│   │       ├── autonomous_user.py   (Phase 4 で追加, @tool) ✅
│   │       └── interactive_obo.py   (Phase 5 で追加, @tool) ✅
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
│       └── call_foundry_agent.py  # POST /autonomous/app + /autonomous/app/stream（force_tool でツール選択可能）✅
├── frontend/                # Phase 1〜: SPA（React + TypeScript）
│   ├── scripts/
│   │   └── deploy-swa.py       # SWA デプロイスクリプト（.env.production 生成 → Vite ビルド → swa deploy）✅
│   └── src/
│       ├── authConfig.ts
│       ├── App.tsx               # Phase 5: 3 タブ UI（autonomous-agent / interactive-obo / no-agent）✅
│       ├── api/
│       │   ├── identityEchoApi.ts
│       │   ├── backendApi.ts        (Phase 3 で追加) ✅ SSE ストリーミング対応
│       │   └── foundryAgentApi.ts   (Phase 5 で追加) ✅ SPA → Foundry Agent API 直接呼び出し（OBO 用）
│       ├── components/
│       │   ├── CallerInfo.tsx
│       │   ├── AutonomousChatPanel.tsx (Phase 3 で追加) ✅ チャット形式 UI + ツール選択（App/User/Debug）
│       │   ├── InteractiveOboPanel.tsx (Phase 5 で追加) ✅ Interactive OBO 専用チャットパネル
│       │   ├── TokenChainSteps.tsx     (Phase 2B+ で追加) ✅
│       │   └── TopBar.tsx              ✅ ナビゲーションバー
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
    "tokenKind": "delegated",
    "oid": "...",
    "upn": "alice@contoso.com",
    "appId": "...",
    "scopes": ["CallerIdentity.Read"],
    "roles": []
  },
  "accessToken": {
    /* 全 JWT claims */
  },
  "humanReadable": "alice@contoso.com の委任権限 (CallerIdentity.Read) でアクセスされました"
}
```

> **レスポンス形式の詳細**は設計書 §4.4 を参照。

**`tokenKind` の判定ロジック（実装済み）**

受け取った JWT の `scp` claim の有無で `tokenKind` を判定するシンプルなロジック:

```python
def _determine_token_kind(claims: dict) -> str:
    has_scp = bool(claims.get("scp"))
    if not has_scp:
        return "app_only"    # Application Permission（Autonomous Agent App フロー）
    return "delegated"       # Delegated Permission（Interactive / Autonomous Agent User フロー）
```

| TR の特徴        | `tokenKind` |
| ---------------- | ----------- |
| `scp` claim なし | `app_only`  |
| `scp` claim あり | `delegated` |

> **設計からの変更点**: 当初は `ENTRA_AGENT_ID_USER_UPN` 環境変数との照合で 3 種の `callerType` を判定する設計だったが、`scp` claim の有無のみで `tokenKind` を判定する方式に簡素化した。`delegated_human_user` と `delegated_agent_user` の区別は行わず、caller の `upn` 値で判断可能。

#### App Registration（新規作成）

| 登録名                   | 種別                 | 設定                        |
| ------------------------ | -------------------- | --------------------------- |
| `demo-client-app`        | SPA（Public Client） | リダイレクト URI、PKCE 有効 |
| `demo-identity-echo-api` | Web API              | App ID URI、スコープ定義    |

> **スコープ設計方針**: Identity Echo API の App Registration には以下の**デモ専用スコープ**を定義する。Microsoft Graph 等の実際のリソースにアクセスせず、完結したデモ環境を構築できる。
>
> | スコープ                  | 種別                   | 使用フェーズ                                                             |
> | ------------------------- | ---------------------- | ------------------------------------------------------------------------ |
> | `CallerIdentity.Read`     | Delegated Permission   | Phase 1（SPA）、Phase 4（Autonomous Agent User）、Phase 5（Interactive） |
> | `CallerIdentity.Read.All` | Application Permission | Phase 2（Autonomous Agent App）                                          |

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
  - JWT クレームから `tokenKind` / `oid` / `upn` / `appId` / `scopes` / `roles` を組み立てて JSON レスポンス
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
- [x] `GET /api/resource` に Bearer トークン付与 → `tokenKind: "delegated"` が返ることを確認 — ⬜ ブラウザでの手動確認が必要

#### 切り分けポイント

| 問題                                      | 原因の候補                                                                                                                                     |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| MSAL のログインが動かない                 | リダイレクト URI の不一致、テナント ID の誤り                                                                                                  |
| トークンが Identity Echo API に拒否される | `aud` の不一致（`requested_access_token_version = 2` では `aud` は生の Client ID (GUID) であり `api://` URI ではない点に注意）、`iss` の不一致 |
| CORS エラー                               | Identity Echo API の CORS 設定漏れ                                                                                                             |

---

### Phase 2: Foundry Hosted Agent 最小実装（Autonomous Agent App Flow）

> **詳細**: [Autonomous Agent App Flow 実装計画書](autonomous-agent-app-flow-implementation-plan.md)

✅ 完了。Foundry Hosted Agent のコンテナ内で **T1 取得 → TR 取得（client_credentials）→ Identity Echo API 呼び出し**の E2E パスを確立。

**サブステップ概要**:

| #       | サブステップ                       | 新たに検証する概念                              | ステータス |
| ------- | ---------------------------------- | ----------------------------------------------- | ---------- |
| **A-1** | インフラプロビジョニング           | ACR, Capability Host, RBAC                      | ✅ 完了    |
| **A-2** | Agent コード + ローカルテスト      | Agent Framework, hosting adapter, `@tool`       | ✅ 完了    |
| **A-3** | Foundry デプロイ + MSI 確認        | Docker build, ACR push, Foundry ランタイム, MSI | ✅ 完了    |
| **A-4** | Identity Echo API クラウドデプロイ | Container Apps Environment, Dockerfile, Ingress | ✅ 完了    |
| **B**   | Resource API 統合                  | T1/TR Token Exchange, Entra Agent ID            | ✅ 完了    |
| **C**   | Backend API 統合 + curl テスト     | Foundry SDK 呼び出し, E2E パス                  | ✅ 完了    |

**主要な実証結果**:

- T1 取得: Project MI → FIC 経由で Blueprint の T1 を正常取得（手動 FIC 登録が必要と判明）
- TR 取得: `client_credentials` で `CallerIdentity.Read.All`（Application Permission）を含む app-only トークンを取得
- Identity Echo API: `tokenKind: "app_only"`, Agent Identity OID を正しく識別
- Backend API: SSE ストリーミング対応（`POST /api/demo/autonomous/app/stream`）

---

### Phase 3: SPA + Autonomous Agent App Flow 統合（E2E）

> **詳細**: [Autonomous Agent App Flow 実装計画書](autonomous-agent-app-flow-implementation-plan.md)

✅ 完了。Phase 1 の SPA と Phase 2 の Backend API + Foundry Hosted Agent を接続し、**Autonomous Agent App Flow のエンドツーエンド**を完成。ローカル E2E + クラウドデプロイ（SWA + Container Apps）完了。

**完成した E2E フロー**:

```text
👤 ユーザー（ログイン不要）
  → [チャット送信] → SPA (AutonomousChatPanel)
  → POST /api/demo/autonomous/app/stream → Backend API (MSI token, SSE)
  → Foundry Hosted Agent → T1 → TR → Identity Echo API
  ← SSE ストリーミング → SPA リアルタイム表示
```

---

### Phase 4: Autonomous Agent User Flow 追加

> **詳細**: [Autonomous Agent User Flow 実装計画書](autonomous-agent-user-flow-implementation-plan.md)

✅ 完了。Agent User の委任権限で動作する Autonomous Agent User Flow を追加する。

**実装状況**:

- ✅ Agent Runtime: `autonomous_user.py` ツール、`exchange_user_t2()` / `exchange_user_token()` トークン交換関数
- ✅ Agent Runtime: `main.py` に `call_resource_api_autonomous_user` ツール登録済み
- ✅ Frontend: `AutonomousChatPanel` にツール選択 UI（Auto / App / **User** / Debug）を追加済み
- ✅ Backend API: `force_tool` パラメータで既存エンドポイント経由でツール選択可能
- ✅ Agent User 作成済み（`create-agent-user.py`）
- ✅ Agent User への consent 付与済み（`grant-consent-to-agent-identity.py`）

**追加するコンセプト**:

- **Agent User**: テナント内の専用ユーザーアカウント（`agentuser@contoso.com`）
- **Agent User FIC（`user_fic`）**: T1 → T2 → TR（`grant_type=user_fic`）で Agent User の委任権限を取得

**Token Exchange チェーン**: `get_t1()` → `exchange_user_t2(t1)` → `exchange_user_token(t1, t2, username)` → TR（delegated, sub = Agent User）

**期待する `tokenKind`**: `delegated`（caller の `upn` が Agent User の UPN）

---

### Phase 5: Interactive Flow（OBO）

> **詳細**: [Interactive OBO Flow 実装計画書](interactive-obo-implementation-plan.md)

✅ 完了。人間ユーザー自身の委任権限で、エージェントがリソース API を呼び出す Interactive OBO Flow を実装。

**アーキテクチャ**（Autonomous Flow とは異なり、SPA → Foundry Agent API を直接呼び出し）:

```text
👤 ユーザー（ログイン必須）
  → MSAL: Tc (Blueprint scope) + Foundry API トークン (ai.azure.com scope) を取得
  → Foundry Agent API を直接呼び出し（metadata に Tc をチャンキング格納）
  → Hosted Agent: T1 + Tc → TR（OBO, jwt-bearer） → Identity Echo API
  ← SSE ストリーミング → SPA リアルタイム表示
```

**主要な実装ポイント**:

- Blueprint に `access_agent` スコープを公開（`set-blueprint-scope.py`）
- metadata 値の 512 文字制限 → Tc を 500 文字ごとにチャンキング分割
- Agent Identity → Resource API に `AllPrincipals` Admin Consent が必要
- SPA → Foundry Agent API は CORS `Access-Control-Allow-Origin: *` で動作確認済み

**期待する `tokenKind`**: `delegated`（caller の `upn` がログインユーザーの UPN）

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
| Phase 4  | Agent User アカウント（`agentuser@contoso.com`）                                                                                                            | Autonomous Agent User Flow                                        |
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
- [x] デプロイ後 E2E 確認: SPA ログイン → Identity Echo API 呼び出し → `tokenKind: "delegated"` を確認 — ✅ ブラウザでの手動確認完了

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
- [x] Foundry Agent API 経由で `call_resource_api_autonomous_app` の E2E テスト — ✅ Step B で確認済み（`tokenKind: "app_only"`, `oid: 6fac9afc-...`）

**Step C: Backend API**

- [x] Backend API のコーディング（`src/backend_api/`） — ✅ config.py, foundry_client.py, routes/demo.py, main.py, requirements.txt 作成済み
- [x] SSE ストリーミング対応（`POST /api/demo/autonomous/app/stream`） — ✅ OpenAI Responses API イベントを SSE フレームとして中継
- [x] Backend API の `Dockerfile` を作成 — ✅ `python:3.11-slim` + `uvicorn`
- [x] ローカル E2E 確認: 一括レスポンス + SSE ストリーミングの両方で `tokenKind: "app_only"` を確認 — ✅ 検証済み
- [x] Backend API を同一 Container Apps 環境にデプロイ（`terraform apply`） — ✅ apply 済み
- [x] Backend API の Container App に**専用 UAMI（`uami-ca-foundry-*`）をアタッチ** — ✅ `AZURE_CLIENT_ID` env で `DefaultAzureCredential()` が選択
- [x] Backend API の専用 UAMI に Foundry **Account** スコープで `Cognitive Services User` ロールを付与 — ✅ apply 済み
- [x] デプロイ後確認: `GET /health` → `{"status": "ok"}` — ✅ 確認済み（コールドスタート約 10 秒）
- [x] デプロイ後確認: `POST /api/demo/autonomous/app` に curl → `tokenKind: "app_only"` を確認 — ✅ E2E 成功（`oid: 6fac9afc-...`, `roles: ["CallerIdentity.Read.All"]`）
- [x] デプロイ後確認: `POST /api/demo/autonomous/app/stream` に curl → SSE イベントがストリーミングで返ることを確認 — ✅ `response.created` → `function_call` → `function_call_output` → `output_text.delta` (逐次) → `response.completed`

#### Phase 3 デプロイ

- [x] Backend API の CORS 許可オリジンに `http://localhost:5173`, `http://localhost:4173` を追加 — ✅ `src/backend_api/main.py` に `CORSMiddleware` 追加済み
- [x] SPA に Autonomous Agent App チャット UI を追加 — ✅ `AutonomousChatPanel.tsx` + `backendApi.ts`（SSE ストリーミング）+ `extractAgentToolOutput.ts`（ヘルパー）、タブ UI（`autonomous-app` / `identity-echo-debug`）
- [x] ローカル E2E 確認: SPA チャット UI → Backend API → Foundry Agent → Identity Echo API の順に動作を確認 — ✅ `http://localhost:5173` からの SSE ストリーミング E2E 成功
- [x] クラウドデプロイ: Backend API の CORS 許可オリジンに Static Web Apps の URL を追加して再デプロイ — ✅ `FRONTEND_SPA_APP_URL` 環境変数による動的 CORS 設定を実装。Terraform で SWA URL を Container App に自動注入。`deploy-container-apps.py` で再デプロイ済み
- [x] クラウドデプロイ: Identity Echo API の CORS 許可オリジンにも SWA URL を追加して再デプロイ — ✅ 同じ `FRONTEND_SPA_APP_URL` パターンで実装（`9e72b78` で修正）
- [x] クラウドデプロイ: SPA を Static Web Apps にデプロイ — ✅ `deploy-swa.py` でクラウド API URL を `.env.production` にベイク → SWA デプロイ（`https://mango-stone-090b84403.4.azurestaticapps.net`）
- [x] クラウド E2E 確認: デプロイ済み SPA → Backend API → Foundry Agent → Identity Echo API の E2E を確認 — ✅ ブラウザでの手動確認完了

#### Phase 4 デプロイ

- [x] Agent Runtime に `call_resource_api_autonomous_user` ツール + トークン交換関数を実装 — ✅ `autonomous_user.py` + `exchange_user_t2()` / `exchange_user_token()` 実装済み
- [x] Frontend の `AutonomousChatPanel` にツール選択 UI（User）を追加 — ✅ `force_tool` パラメータで既存の Backend API エンドポイント経由でツール選択可能（専用エンドポイント追加は不要と判断）
- [x] Agent User を作成し consent を付与して Agent を再デプロイ — ✅ `create-agent-user.py` + `grant-consent-to-agent-identity.py` 実行済み
- [x] E2E テスト: `POST /api/demo/autonomous/app` + `force_tool=call_resource_api_autonomous_user` → `tokenKind: "delegated"`, `upn: "agentuser@..."` を確認 — ✅ E2E 確認済み

#### Phase 5 デプロイ

- [x] SPA に Interactive シナリオ UI（Foundry Agent 直接呼び出し）を追加して再デプロイ — ✅ `InteractiveOboPanel.tsx` + `foundryAgentApi.ts`（SPA → Foundry Agent API 直接呼び出し、metadata チャンキング）
- [x] CORS 事前確認: Foundry Agent API エンドポイントへのブラウザからの `OPTIONS` リクエストが通ることを確認 — ✅ `Access-Control-Allow-Origin: *` 確認済み

#### Phase 6 デプロイ

- [ ] Backend API の全ルートハンドラを `async def` に変更して再デプロイ
- [ ] SPA にトークンフロー可視化・比較モード UI を追加して再デプロイ

### 4.3 環境変数まとめ

| コンポーネント       | 変数名                                     | 設定値の例 / 取得元                                                                |
| -------------------- | ------------------------------------------ | ---------------------------------------------------------------------------------- |
| Identity Echo API    | `ENTRA_TENANT_ID`                          | Entra ID テナント ID                                                               |
| Identity Echo API    | `ENTRA_RESOURCE_API_CLIENT_ID`             | `demo-identity-echo-api` App Registration の Client ID                             |
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
| Foundry Hosted Agent | `ENTRA_AGENT_ID_USER_UPN`                  | `agentuser@contoso.com`（Phase 4 以降、Agent User 識別用）                         |
| Frontend SPA         | `BACKEND_API_URL`                          | Backend API の URL（ローカル: `http://localhost:8000`、Azure: Container Apps URL） |
| Frontend SPA         | `ENTRA_SPA_APP_CLIENT_ID`                  | `demo-client-app` の Client ID                                                     |
| Frontend SPA         | `ENTRA_TENANT_ID`                          | Entra ID テナント ID                                                               |
| Frontend SPA         | `RESOURCE_API_URL`                         | Identity Echo API の Container Apps URL                                            |
| Frontend SPA         | `ENTRA_RESOURCE_API_SCOPE`                 | `api://{id}/CallerIdentity.Read`（Identity Echo API スコープ）                     |
| Frontend SPA         | `ENTRA_RESOURCE_API_CLIENT_ID`             | `demo-identity-echo-api` の Client ID                                              |
| Frontend SPA         | `ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID` | Blueprint の Application ID（Interactive OBO 用 Tc 取得）                          |
| Frontend SPA         | `FOUNDRY_PROJECT_ENDPOINT`                 | Foundry Project Endpoint（SPA → Foundry Agent API 直接呼び出し用）                 |
| Frontend SPA         | `FOUNDRY_AGENT_NAME`                       | Hosted Agent 名（デフォルト: `demo-entraagtid-agent`）                             |

> **Vite 環境変数の注記**: SPA は `VITE_` プレフィックスではなく、`vite.config.ts` の `envPrefix: ['ENTRA_', 'RESOURCE_API_', 'FOUNDRY_', 'BACKEND_']` で定義されたプレフィックスを使用する。`.env` ファイルは `src/` ディレクトリに配置し、全コンポーネントで共有する（`envDir: '../'`）。Phase 3 で `BACKEND_API_URL` を追加済み。Phase 5 で `ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID`、`FOUNDRY_PROJECT_ENDPOINT`、`FOUNDRY_AGENT_NAME` を追加済み。
>
> **クラウドデプロイ時の変数注入**: `deploy-swa.py` が `src/.env` のローカル URL を Terraform output のクラウド URL に置換した `.env.production` を生成し、Vite ビルド時に埋め込む。Container Apps の `FRONTEND_SPA_APP_URL` は Terraform が SWA リソースの `default_host_name` から自動算出して注入する。

---

## 5. 参考：フローごとの呼び出し主体対比

|                                     | Interactive                                       | Autonomous Agent App          | Autonomous Agent User                 |
| ----------------------------------- | ------------------------------------------------- | ----------------------------- | ------------------------------------- |
| Foundry Agent API の呼び出し主体    | SPA（ユーザーの MSAL token）                      | Backend API（MSI token）      | Backend API（MSI token）              |
| T1 取得に使う credential            | Foundry Project MSI（`DefaultAzureCredential()`） | 同左                          | 同左                                  |
| TR 取得フロー                       | OBO（T1 + Tc → TR）                               | client_credentials（T1 → TR） | user_fic（T1 → T2 → TR）              |
| Identity Echo API が認識する caller | 人間ユーザー（`alice@contoso.com`）               | Agent Identity（OID）         | Agent User（`agentuser@contoso.com`） |
| `tokenKind`                         | `delegated`                                       | `app_only`                    | `delegated`                           |
