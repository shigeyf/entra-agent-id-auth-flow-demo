# Architecture

[English](./architecture.md) | [日本語](./architecture.ja.md)

Entra Agent ID デモアプリのアーキテクチャ概要です。

## コンポーネント構成

```text
┌─────────────────────────────────────────────────────────────┐
│  Frontend SPA (React + MSAL.js)                             │
│  Azure Static Web Apps                                      │
└──────────┬──────────────────────────────┬───────────────────┘
           │ Autonomous Flow              │ Interactive Flow
           ▼                              │
┌─────────────────────┐                   │
│  Backend API        │                   │
│  (FastAPI)          │                   │
│  Container Apps     │                   │
└──────────┬──────────┘                   │
           │                              │
           ▼                              ▼
┌────────────────────────────────────────────────────────────┐
│  Foundry Agent Service (Hosted Agent, Responses API)       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Token Exchange (MI Token → TR)                       │  │
│  │  Autonomous (App):  Agent 自身の権限で TR 取得       │  │
│  │  Autonomous (User): Agent User の委任権限で TR 取得  │  │
│  │  Interactive:    ユーザーの Tc を使い OBO で TR 取得 │  │
│  └──────────────────────┬───────────────────────────────┘  │
└─────────────────────────┼──────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────┐
│  Identity Echo API (FastAPI)                               │
│  Container Apps                                            │
│  → Bearer トークンの caller 情報を返却                     │
└────────────────────────────────────────────────────────────┘
```

## コンポーネント一覧

| コンポーネント           | 技術                     | ホスティング          | 役割                                                   |
| ------------------------ | ------------------------ | --------------------- | ------------------------------------------------------ |
| **Frontend SPA**         | React 19 + MSAL.js       | Azure Static Web Apps | UI、ユーザー認証、フロー切り替え                       |
| **Backend API**          | FastAPI (Python)         | Azure Container Apps  | Autonomous フローの仲介 (MSI で Foundry 認証)          |
| **Identity Echo API**    | FastAPI (Python)         | Azure Container Apps  | Bearer トークンの caller 情報を返却 (Resource API)     |
| **Foundry Hosted Agent** | Agent Framework (Python) | Foundry Agent Service | トークン取得 (Entra Agent ID)・API 呼び出し・LLM 整形  |
| **Microsoft Entra ID**   | —                        | Azure                 | 認証・認可基盤 (Blueprint, Agent Identity, Agent User) |

---

## データフロー

### 呼び出し経路の違い

Foundry Agent API を **誰が呼び出すか** がフローごとに異なります:

| 観点                         | Interactive                  | Autonomous (App / User)        |
| ---------------------------- | ---------------------------- | ------------------------------ |
| Foundry API を呼び出す主体   | ユーザー本人 (MSAL トークン) | Backend API (Managed Identity) |
| Frontend の役割              | 認証 + Foundry 直接呼び出し  | トリガー送信と結果表示のみ     |
| ユーザートークン (Tc) の有無 | あり (OBO の入力)            | なし                           |

### Interactive Flow

```text
ユーザー → Frontend (MSAL ログイン)
         → Foundry Agent API (Bearer = ユーザーの Entra ID トークン)
           ├─ Tc をメッセージペイロードで受け渡し
           ├─ T1 取得 (Project MSI)
           ├─ OBO 交換 (T1 + Tc → TR, sub = ユーザー本人)
           └─ Identity Echo API (Bearer TR)
              → caller: alice@contoso.com (delegated)
```

### Autonomous Agent App Flow

```text
ユーザー → Frontend (認証不要)
         → Backend API (POST /api/demo/autonomous/app)
           → Foundry Agent API (Bearer = MSI トークン)
             ├─ T1 取得 (Project MSI)
             ├─ client_credentials (T1 → TR, sub = Agent Identity)
             └─ Identity Echo API (Bearer TR)
                → caller: Agent Identity SP (app-only)
```

### Autonomous Agent User Flow

```text
ユーザー → Frontend (認証不要)
         → Backend API (POST /api/demo/autonomous/app)
           → Foundry Agent API (Bearer = MSI トークン)
             ├─ T1 取得 (Project MSI)
             ├─ client_credentials (T1 → T2)
             ├─ user_fic (T2 → TR, sub = Agent User)
             └─ Identity Echo API (Bearer TR)
                → caller: agentuser@contoso.com (delegated)
```

---

## 認証フロー概要

3 つのフローで Identity Echo API に到達するトークンの subject が異なります:

| フロー                | Token Exchange                  | TR の subject                         | トークン種別 |
| --------------------- | ------------------------------- | ------------------------------------- | ------------ |
| Interactive           | T1 + Tc → TR (OBO / jwt-bearer) | 人間ユーザー (`alice@contoso.com`)    | delegated    |
| Autonomous Agent App  | T1 → TR (client_credentials)    | Agent Identity (サービスプリンシパル) | app-only     |
| Autonomous Agent User | T1 → T2 → TR (user_fic)         | Agent User (`agentuser@contoso.com`)  | delegated    |

> 詳細なシーケンス図・プロトコル仕様は
> [Agent Identity OAuth フロー比較](agent-identity-oauth-flow-comparison.ja.md) を参照してください。

### Entra ID エンティティ

| エンティティ                       | 種別                        | 役割                                                              |
| ---------------------------------- | --------------------------- | ----------------------------------------------------------------- |
| Agent Identity Blueprint           | App Registration            | Agent Identity の親。FIC・スコープ・Application Consent を保持    |
| Agent Identity                     | Service Principal           | Blueprint から派生。トークン取得の主体                            |
| Agent User                         | `microsoft.graph.agentUser` | 特定の Agent Identity にのみ impersonate を許可される特殊ユーザー |
| SPA App Registration               | App Registration            | Frontend SPA の MSAL 認証用                                       |
| Identity Echo API App Registration | App Registration            | Resource API の audience・スコープ・App Role 定義                 |

---

## Azure リソース構成

Terraform (`src/infra/`) で以下のリソースをプロビジョニングします:

| リソース                             | 説明                                                 |
| ------------------------------------ | ---------------------------------------------------- |
| Resource Group                       | 全リソースのコンテナ                                 |
| Entra ID App Registration × 2        | SPA 用・Identity Echo API 用                         |
| Foundry Resource (Cognitive Account) | Microsoft Foundry メインリソース (AIServices)        |
| Foundry Project                      | Agent Identity Blueprint + Agent Identity を自動作成 |
| Capability Host                      | Hosted Agent の実行環境                              |
| Model Deployment                     | LLM モデル (例: gpt-4.1)                             |
| Azure Container Registry             | Agent・API のコンテナイメージ                        |
| Container Apps Environment + Apps    | Backend API / Identity Echo API                      |
| Static Web App                       | Frontend SPA                                         |
| Log Analytics + Application Insights | 監視・ログ                                           |
| RBAC Role Assignments                | サービス間のアクセス権限                             |

---

## プロジェクト構成

```text
src/
├── frontend/          # React SPA (Vite + MSAL.js)
├── backend_api/       # Backend API (FastAPI) — Foundry Agent 呼び出しの仲介
├── identity_echo_api/ # Identity Echo API (FastAPI) — トークン検証・caller 情報返却
├── agent/             # Foundry Hosted Agent (runtime + deploy scripts)
│   ├── runtime/       #   Agent 実行コード (main.py, tools/)
│   ├── entra-agent-id/#   Entra Agent ID セットアップスクリプト群
│   └── scripts/       #   デプロイ・呼び出しスクリプト
├── infra/             # Terraform (Azure リソース定義)
└── scripts/           # デプロイ自動化スクリプト
docs/                  # アーキテクチャ・OAuth フロー解説
labs/                  # Entra Agent ID ハンズオンラボ
```

各コンポーネントの詳細は README を参照してください:

- [Frontend SPA](../src/frontend/README.ja.md)
- [Backend API](../src/backend_api/README.ja.md)
- [Identity Echo API](../src/identity_echo_api/README.ja.md)
- [Hosted Agent](../src/agent/README.ja.md)

---

## 関連ドキュメント

- [Getting Started](getting-started.ja.md) — 環境構築・デプロイの一本道ガイド
- [Agent Identity OAuth フロー比較](agent-identity-oauth-flow-comparison.ja.md) — シーケンス図・プロトコル詳細
- [再デプロイ・運用リファレンス](deployment.ja.md) — コンポーネント別のデプロイ手順
