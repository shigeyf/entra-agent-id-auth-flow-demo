# Entra Agent ID デモアプリ — Foundry Hosted Agent

[English](./README.md) | [日本語](./README.ja.md)

Microsoft Entra Agent ID の 3 つの認証フローを可視化するデモアプリケーションです。

[Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/what-is-foundry) の Hosted Agent と [Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/) を使い、**「誰の権限でリソース API にアクセスしたか」** をリアルタイムに比較できます。

## デモが示すもの

同一のエージェント (Agent Identity) が 3 つの認証フローを切り替えて動作し、リソース API (Identity Echo API) が**誰からのアクセスと認識したか**を可視化します。

| シナリオ                  | フロー             | API が認識する呼び出し元                   | トークン種別 |
| ------------------------- | ------------------ | ------------------------------------------ | ------------ |
| **Interactive Agent**     | OBO (On-Behalf-Of) | 人間ユーザー本人 (例: `alice@contoso.com`) | delegated    |
| **Autonomous Agent App**  | client_credentials | Agent Identity 自身 (サービスプリンシパル) | app-only     |
| **Autonomous Agent User** | user_fic           | Agent User (例: `agentuser@contoso.com`)   | delegated    |

これは Entra Agent ID のコアバリュー — **1 つのエージェントが、呼び出し文脈に応じて異なる権限コンテキストを使い分けられる** — を体現しています。

## アーキテクチャ

```text
┌─────────────────────────────────────────────────────────────┐
│  Frontend SPA (React + MSAL.js)                             │
│  Azure Static Web Apps                                      │
└──────────┬──────────────────────────────┬───────────────────┘
           │ (システムトリガーを模倣)     │ Interactive Flow
           ▼                              │
┌─────────────────────┐                   │
│  Backend API        │                   │
│  (FastAPI)          │                   │
│  Container Apps     │                   │
└──────────┬──────────┘                   │
           │ Autonomous Flow              │
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

## 技術スタック

| コンポーネント    | 技術                                                                   |
| ----------------- | ---------------------------------------------------------------------- |
| Frontend          | React 19 + TypeScript + Vite + MSAL.js                                 |
| Backend API       | FastAPI (Python) — SPA からの Autonomous フロー仲介                    |
| Identity Echo API | FastAPI (Python) — Bearer トークンの caller 情報を返却                 |
| Agent             | Microsoft Foundry Hosted Agent (`azure-ai-agentserver-agentframework`) |
| Infrastructure    | Terraform (azurerm + azapi + azuread)                                  |
| 認証              | Microsoft Entra ID, MSAL, Entra Agent ID                               |
| CI/CD             | Python スクリプトによるデプロイ自動化                                  |

## プロジェクト構成

| ディレクトリ                                                 | 説明                                                             |
| ------------------------------------------------------------ | ---------------------------------------------------------------- |
| [src/frontend/](src/frontend/README.ja.md)                   | React SPA (Vite + MSAL.js)                                       |
| [src/backend_api/](src/backend_api/README.ja.md)             | Backend API (FastAPI) — Foundry Agent 呼び出しの仲介             |
| [src/identity_echo_api/](src/identity_echo_api/README.ja.md) | Identity Echo API (FastAPI) — トークン検証・caller 情報返却      |
| [src/agent/](src/agent/README.ja.md)                         | Foundry Hosted Agent (runtime + deploy + entra-agent-id scripts) |
| [src/infra/](src/infra/README.ja.md)                         | Terraform (Azure リソース定義)                                   |
| src/scripts/                                                 | デプロイ自動化スクリプト                                         |
| docs/                                                        | アーキテクチャ・OAuth フロー解説                                 |
| labs/                                                        | Entra Agent ID ハンズオンラボ (手動フロー確認用)                 |

## クイックスタート

### 前提条件

#### Azure / Entra ID の権限

| 対象                     | 必要な権限                    | 用途                                                                                                                          |
| ------------------------ | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Azure サブスクリプション | **Contributor**               | リソースグループ、Foundry、Container Apps、ACR 等の作成                                                                       |
| Azure サブスクリプション | **User Access Administrator** | サービス間 RBAC ロール割り当て (Managed Identity → ACR、Foundry 等)                                                           |
| Entra ID テナント        | **Application Administrator** | App Registration の作成・API スコープ定義、Entra Agent ID セットアップ (Blueprint FIC 設定、App Role 付与、Agent User 作成等) |

#### 方法 A: Dev Container / GitHub Codespaces（推奨）

Dev Container を使うと、必要なツール (Terraform, Azure CLI, Node.js, Python, uv, Docker) がすべてプリインストールされた環境が立ち上がります。追加のインストールは不要です。

- **GitHub Codespaces**: リポジトリページから「Code」→「Codespaces」で起動
- **VS Code + Dev Container**: [Dev Containers 拡張機能](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) をインストールし、「Reopen in Container」で起動

> Dev Container は `postCreateCommand` で `uv sync` と `poe setup` を自動実行するため、Python 依存パッケージと pre-commit hooks は起動時にセットアップ済みです。

#### 方法 B: ローカル環境

以下のツールを手動でインストールしてください:

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.9
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) (ログイン済み)
- [Node.js](https://nodejs.org/) >= 20
- [Python](https://www.python.org/) >= 3.12 + [uv](https://docs.astral.sh/uv/)
- [Docker](https://docs.docker.com/get-docker/) (Hosted Agent ビルド時)

### セットアップ手順

> **注意**: Entra Agent ID の 3 フローを試すには Azure へのデプロイが必要です。
> Foundry Hosted Agent は Azure 上でのみ動作するため、ローカル実行だけではデモの主要機能を利用できません。

1. リポジトリのクローンと依存パッケージのインストール
2. Terraform でインフラをプロビジョニング (Container Apps もこの時点でデプロイされる)
3. Graph API 操作用アプリの登録 (Prereqs Terraform)
4. Terraform 出力を `.env` に同期
5. Entra Agent ID のセットアップ (Blueprint FIC 設定等)
6. Hosted Agent をデプロイ
7. Frontend SPA をデプロイ

詳細な手順は [docs/getting-started.ja.md](docs/getting-started.ja.mdmd) を参照してください。
再デプロイ・運用については [docs/deployment.ja.md](docs/deployment.ja.mdmd) を参照してください。

## ドキュメント

| ドキュメント                                                                            | 内容                                         |
| --------------------------------------------------------------------------------------- | -------------------------------------------- |
| [Getting Started](docs/getting-started.ja.md)                                           | 前提条件・環境構築・ローカル起動の完全ガイド |
| [Deployment](docs/deployment.ja.md)                                                     | 再デプロイ・運用リファレンス                 |
| [Architecture](docs/architecture.ja.md)                                                 | コンポーネント構成・データフロー詳細         |
| [Infrastructure](docs/infrastructure.ja.md)                                             | Terraform インフラ構成・変数の読解ガイド     |
| [Entra Agent ID Overview](docs/entra-agent-id-overview.ja.md)                           | Entra Agent ID 概念と 3 フロー概要           |
| [Agent Identity OAuth Flow Comparison](docs/agent-identity-oauth-flow-comparison.ja.md) | 3 フローのプロトコル詳細・シーケンス図       |

## License

[MIT](LICENSE)
