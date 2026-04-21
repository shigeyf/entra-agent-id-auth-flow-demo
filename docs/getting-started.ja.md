# Getting Started

[English](./getting-started.md) | [日本語](./getting-started.ja.md)

このガイドでは、Entra Agent ID デモアプリの環境構築からデプロイまでの手順を説明します。

> **注意**: Entra Agent ID の 3 フローを試すには Azure へのデプロイが必要です。
> Foundry Hosted Agent は Azure 上でのみ動作するため、ローカル実行だけではデモの主要機能を利用できません。

## 前提条件

### Azure アカウント・権限

| 対象                     | 必要な権限                                                                 | 用途                                                                                                                                                                                                 |
| ------------------------ | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Azure サブスクリプション | **Owner**、または **Contributor** + **User Access Administrator**          | リソースグループ、Foundry、Container Apps、ACR、SWA 等の作成、およびサービス間 RBAC ロール割り当て (Managed Identity → ACR、Foundry 等)                                                              |
| Entra ID テナント        | **Application Administrator** (最低限 **Cloud Application Administrator**) | App Registration・Enterprise Application (Service Principal) の作成、Application ID URI の設定、API スコープ定義、Entra Agent ID セットアップ (Blueprint FIC 設定、App Role 付与、Agent User 作成等) |
| Azure CLI                | `az login` 済み                                                            | Terraform、デプロイスクリプトが使用                                                                                                                                                                  |

> **Entra Agent ID 関連スクリプト**: `set-blueprint-fic.py` 等のセットアップスクリプトは
> MSAL 対話ログインで Graph API 委任スコープ (`AgentIdentityBlueprint.ReadWrite.All` 等) を取得します。
> Application Administrator ロールがあればこれらの操作は実行可能です。
>
> **別テナントへのデプロイ時の注意**: Terraform による Service Principal の作成や Identifier URI の
> 設定で `Authorization_RequestDenied` (403) エラーが発生する場合、対象テナントでの Entra ID
> ディレクトリロールが不足しています。テナント管理者に最低限 **Cloud Application Administrator**
> ロールの割り当てを依頼してください。また、Entra 管理センター (Identity → Users → User settings)
> で **「ユーザーがアプリケーションを登録できる」** が **Yes** になっていることを確認してください。
>
> | エラーメッセージ                                                                      | 原因                                                      | 必要なロール                         |
> | ------------------------------------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------ |
> | `backing application of the service principal being created must in the local tenant` | Enterprise Application (Service Principal) の作成権限不足 | Cloud Application Administrator 以上 |
> | `Insufficient privileges to complete the operation` (Identifier URI)                  | Application ID URI (`api://...`) の設定権限不足           | Cloud Application Administrator 以上 |

### 開発ツール

| ツール        | バージョン                   | インストール                                                                 |
| ------------- | ---------------------------- | ---------------------------------------------------------------------------- |
| **Terraform** | >= 1.9, < 2.0                | [Install Terraform](https://developer.hashicorp.com/terraform/install)       |
| **Azure CLI** | 最新                         | [Install Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) |
| **Python**    | >= 3.12                      | [python.org](https://www.python.org/)                                        |
| **uv**        | 最新                         | [Install uv](https://docs.astral.sh/uv/getting-started/installation/)        |
| **Node.js**   | >= 20                        | [nodejs.org](https://nodejs.org/)                                            |
| **Docker**    | 最新 (Hosted Agent ビルド時) | [Install Docker](https://docs.docker.com/get-docker/)                        |

> **Dev Container**: このリポジトリには Dev Container 設定が含まれており、
> VS Code + Dev Containers 拡張機能を使えば上記ツールがすべてプリインストールされた環境を利用できます。

---

## 1. リポジトリのクローンと初期セットアップ

### 方法 A: Dev Container / GitHub Codespaces（推奨）

Dev Container を使うと、必要なツールがすべてプリインストールされ、`postCreateCommand` で Python 依存パッケージ (`uv sync`)、pre-commit hooks、Frontend 依存パッケージ (`npm install`) が自動インストールされます。このセクション (セクション 1) の手順は**すべてスキップ**してセクション 2 に進んでください。

- **GitHub Codespaces**: リポジトリページから「Code」→「Codespaces」で起動
- **VS Code + Dev Container**: [Dev Containers 拡張機能](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) をインストールし、「Reopen in Container」で起動

### 方法 B: ローカル環境

```bash
git clone https://github.com/<org>/microsoft-entra-agent-id.git
cd microsoft-entra-agent-id
```

#### Python 依存パッケージのインストール

```bash
uv sync
```

これにより、`pyproject.toml` に定義されたすべての依存パッケージ (FastAPI, azure-identity, azure-ai-projects 等) と開発ツール (poethepoet, ruff) がインストールされます。

#### Frontend 依存パッケージのインストール

```bash
cd src/frontend
npm install
cd ../..
```

---

## 2. Azure インフラストラクチャのプロビジョニング

### 2-1. Terraform 変数の設定

```bash
cp src/infra/terraform.tfvars.example src/infra/terraform.tfvars
```

`src/infra/terraform.tfvars` を編集します。以下の変数は **必ず設定** してください:

| 変数                            | 説明                               | 例                     |
| ------------------------------- | ---------------------------------- | ---------------------- |
| `tenant_id`                     | Entra ID テナント ID (GUID)        | `"xxxxxxxx-xxxx-..."`  |
| `target_subscription_id`        | Azure サブスクリプション ID (GUID) | `"xxxxxxxx-xxxx-..."`  |
| `location`                      | Azure リージョン                   | `"eastus2"`            |
| `cognitive_project_name`        | Foundry Project 名                 | `"my-foundry-project"` |
| `cognitive_project_description` | Foundry Project の説明             | `"Demo project"`       |
| `cognitive_deployments`         | LLM モデルデプロイ定義             | (example 参照)         |
| `container_apps`                | Container Apps 定義                | (example 参照)         |

その他の変数にはデフォルト値が設定されています。`.tfvars.example` のコメントを参照してください。

> **リージョン**: Microsoft Foundry の Hosted Agent は利用可能なリージョンが限定されています。
> `eastus2` や `swedencentral` など、Foundry Agent Service がサポートするリージョンを選択してください。

### 2-2. Terraform の実行

```bash
cd src/infra
terraform init
terraform plan    # リソース作成内容を確認
terraform apply   # リソースをプロビジョニング
cd ../..
```

> **初回の `terraform apply`** では Container Apps (Backend API / Identity Echo API) のコンテナイメージも
> ACR にビルド・プッシュされ、Container Apps へデプロイされます。

Terraform は以下のリソースを作成します:

| リソース                             | 説明                                                                     |
| ------------------------------------ | ------------------------------------------------------------------------ |
| Resource Group                       | 全リソースのコンテナ                                                     |
| Entra ID App Registration × 2        | SPA 用 (`demo-client-app`) と Resource API 用 (`demo-identity-echo-api`) |
| Foundry Resource (Cognitive Account) | Microsoft Foundry のメインリソース (AIServices)                          |
| Foundry Project                      | Foundry プロジェクト (Agent Identity 含む)                               |
| Capability Host                      | Hosted Agent の実行環境                                                  |
| Model Deployment                     | LLM モデル (例: gpt-4.1)                                                 |
| Azure Container Registry             | Agent および API のコンテナイメージ                                      |
| Container Apps Environment + Apps    | Backend API / Identity Echo API のホスティング                           |
| Static Web App                       | Frontend SPA のホスティング                                              |
| Log Analytics + Application Insights | 監視・ログ                                                               |
| RBAC Role Assignments                | サービス間のアクセス権限                                                 |

---

## 3. Graph API 操作用アプリの登録

Entra Agent ID のセットアップスクリプト (セクション 5) は、Graph API の委任スコープ
(`AgentIdentityBlueprint.ReadWrite.All` 等) を使って Blueprint や Agent Identity を構成します。
これらのスコープを取得するための Public Client App Registration を Terraform で作成します。

```bash
cd labs/entra-agent-id/prereqs
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` を編集し、`tenant_id` を設定してください。

```bash
terraform init
terraform plan
terraform apply
cd ../../..
```

Apply 後に出力される `agent_id_manager_client_id` は、次のセクションで `.env` に設定します。

---

## 4. Terraform 出力を `.env` に同期

Terraform の出力値を `src/.env` に自動同期します:

```bash
cp src/.env.example src/.env
python src/scripts/sync-infra-env.py
```

`sync-infra-env.py` は `src/infra` の `terraform output` から約 15 の環境変数を読み取り、`src/.env` の該当行を上書きします。
手動で値を埋める必要はありませんが、**`.env` ファイルが事前に存在する必要があります**。
設定される変数の一覧は [環境変数リファレンス](#環境変数リファレンス) を参照してください。

次に、セクション 3 で作成した Graph API 操作用アプリの Client ID を `.env` に設定します:

```bash
GRAPH_API_OPS_CLIENT_ID=$(cd labs/entra-agent-id/prereqs && terraform output -raw agent_id_manager_client_id)
sed -i "s|^GRAPH_API_OPS_CLIENT_ID=.*|GRAPH_API_OPS_CLIENT_ID=${GRAPH_API_OPS_CLIENT_ID}|" src/.env
```

> **注意**: `src/.env` は `.gitignore` に含まれており、リポジトリにコミットされません。

---

## 5. Entra Agent ID のセットアップ

Terraform で Foundry Project を作成すると、Agent Identity Blueprint と Agent Identity が自動的にプロビジョニングされます。
ただし、各 OAuth フローを動作させるには以下の追加設定が必要です。

> **OAuth フローの詳細**: 各フローのシーケンス図・プロトコル詳細・公式ドキュメントへのリンクは
> [Agent Identity OAuth フロー比較](agent-identity-oauth-flow-comparison.ja.md) を参照してください。

セットアップスクリプトは `src/agent/entra-agent-id/` にあり、すべて以下の共通仕様です:

- MSAL 対話ブラウザログインで Graph API のトークンを取得 (ブラウザが自動で開きます)
- `src/.env` から必要な環境変数を読み込み
- べき等 — 既に設定済みならスキップ
- `--delete` オプションで設定を元に戻せる

### 5-1. Blueprint FIC の設定（全フロー共通・必須）

Foundry Hosted Agent がトークンを取得するには、Blueprint が Foundry Project の Managed Identity (MSI) を
信頼する必要があります。Federated Identity Credential (FIC) はその信頼関係を登録するものです。

FIC を登録すると、Hosted Agent は MSI の `client_assertion` を使い `client_credentials` グラントで
Exchange Token (T1) を取得できるようになります。T1 は後続の OBO 交換・Autonomous トークン取得の起点です。

```bash
cd src/agent
python entra-agent-id/set-blueprint-fic.py
```

### 5-2. Interactive Agent (OBO) フロー用の設定

Interactive フローでは、ユーザーが SPA でログインし、Hosted Agent がユーザーの委任権限 (delegated) で
Identity Echo API にアクセスします。

#### Blueprint スコープの設定

SPA がユーザーに代わって Hosted Agent を呼び出すには、Blueprint が OAuth2 スコープを公開している必要があります。
このスクリプトは Blueprint に App ID URI (`api://{blueprint-client-id}`) と `access_agent` スコープを設定します。
SPA は `api://{blueprint}/access_agent` スコープを要求してユーザートークン (Tc) を取得します。

```bash
python entra-agent-id/set-blueprint-scope.py
```

#### Agent Identity への Admin Consent 付与

OBO 交換で Agent Identity がユーザーの代理として Identity Echo API にアクセスするには、
テナント管理者の事前同意 (Admin Consent) が必要です。
このスクリプトは `consentType: AllPrincipals` で OAuth2 Permission Grant を作成し、
テナント内の**すべてのユーザー**に対する代理アクセスを許可します。

```bash
python entra-agent-id/grant-admin-consent-to-agent-identity.py
```

### 5-3. Autonomous Agent (App) フロー用の設定

Autonomous Agent App フローでは、ユーザーの介在なしに Agent Identity 自身の権限（application permissions）で
Identity Echo API にアクセスします。

このスクリプトは Identity Echo API の `CallerIdentity.Read.All` App Role を
Agent Identity の Service Principal に付与します。
これにより Agent Identity は `client_credentials` で取得した app-only トークンで API を呼び出せます。

```bash
python entra-agent-id/grant-approle-to-agent-identity.py
```

### 5-4. Autonomous Agent (User) フロー用の設定

Autonomous Agent User フローでは、Agent Identity が Agent User を代理 (impersonate) し、
そのユーザーの delegated 権限で Identity Echo API にアクセスします。

#### Agent User の作成

Agent User は `microsoft.graph.agentUser` という特殊なユーザータイプで、
通常の Entra ID ユーザーとは異なり、特定の Agent Identity にのみ impersonate を許可されます。
事前に `src/.env` で以下を手動設定してください:

| 変数                               | 説明                | 例                                |
| ---------------------------------- | ------------------- | --------------------------------- |
| `ENTRA_AGENT_ID_USER_UPN`          | Agent User の UPN   | `"agent@contoso.onmicrosoft.com"` |
| `ENTRA_AGENT_ID_USER_DISPLAY_NAME` | Agent User の表示名 | `"Demo Agent User"`               |

```bash
python entra-agent-id/create-agent-user.py
```

#### Agent Identity への Delegated Consent 付与

Agent Identity が Agent User の代理で Identity Echo API にアクセスするには、
その Agent User に対する delegated OAuth2 の事前同意が必要です。
このスクリプトは `consentType: Principal` で OAuth2 Permission Grant を作成し、
特定の Agent User に限定した代理アクセスを許可します。

```bash
python entra-agent-id/grant-consent-to-agent-identity.py
```

### 5-5. 設定の確認（オプション）

Blueprint の構成を確認する読み取り専用のスクリプトです。
App ID URI、公開スコープ、FIC、Service Principal の詳細をダンプします:

```bash
python entra-agent-id/inspect-blueprint.py
```

### スクリプト一覧

| スクリプト                                 | 対象フロー            | 説明                                     |
| ------------------------------------------ | --------------------- | ---------------------------------------- |
| `set-blueprint-fic.py`                     | 全フロー共通          | Blueprint に FIC を登録                  |
| `set-blueprint-scope.py`                   | Interactive           | Blueprint に App ID URI + スコープを公開 |
| `grant-admin-consent-to-agent-identity.py` | Interactive           | Admin Consent (AllPrincipals) を付与     |
| `grant-approle-to-agent-identity.py`       | Autonomous Agent App  | App Role を Agent Identity SP に付与     |
| `create-agent-user.py`                     | Autonomous Agent User | Agent User を作成                        |
| `grant-consent-to-agent-identity.py`       | Autonomous Agent User | Delegated Consent (Principal) を付与     |
| `inspect-blueprint.py`                     | (確認用)              | Blueprint の設定をダンプ                 |

---

## 6. Hosted Agent をデプロイ

```bash
cd src/agent
python scripts/deploy-agent.py build push deploy --start --wait
```

これは以下のステップを自動実行します:

1. Docker イメージのビルド (`linux/amd64`)
2. ACR へのプッシュ
3. Foundry Agent Version の作成
4. Agent の起動と起動完了の待機

### 動作確認

#### Autonomous Agent (App) フロー

ユーザーの介在なしに、Agent Identity 自身の権限 (app-only) で Identity Echo API を呼び出します:

```bash
python scripts/invoke-agent.py --tool call_resource_api_autonomous_app
```

#### Autonomous Agent (User) フロー

Agent Identity が Agent User を代理し、delegated 権限で Identity Echo API を呼び出します:

```bash
python scripts/invoke-agent.py --tool call_resource_api_autonomous_user
```

#### Interactive Agent (OBO) フロー

ブラウザが開き MSAL 対話ログインを行った後、ユーザーの委任権限で Identity Echo API を呼び出します:

```bash
python scripts/invoke-interactive-agent.py
```

> `invoke-agent.py` はデフォルトで LLM にツール選択を任せます。
> `--tool` オプションで特定フローを指定できます。

---

## 7. Frontend SPA をデプロイ

```bash
python src/frontend/scripts/deploy-swa.py
```

このスクリプトは以下を自動実行します:

1. `src/.env` からクラウド用の環境変数を読み取り
2. `npm run build` で Vite ビルド (環境変数をバンドルに埋め込み)
3. ビルド成果物を Azure Static Web Apps にデプロイ

> デプロイトークンは `terraform output -raw swa_deployment_token` から自動取得されます。

---

## ローカル開発サーバーの起動

クラウドにデプロイ済みの API を使わず、ローカルで開発・デバッグする場合のサーバー起動手順です。

### Identity Echo API

> **注意**: ローカルで起動した API サーバーは、Azure 上の Hosted Agent からはアクセスできません。
> Hosted Agent は Container Apps にデプロイされた Identity Echo API を呼び出すため、ローカルサーバーは
> API 単体の開発・デバッグや、SPA からの直接呼び出し (No Agent Flow) のテストに限定されます。

```bash
cd src && uvicorn identity_echo_api.main:app --reload --port 8000
```

`http://localhost:8000` で起動します。ヘルスチェック:

```bash
curl http://localhost:8000/health
```

> **`.env` の変更が必要**: `sync-infra-env.py` 実行後は API の URL が Container Apps を指しています。
> ローカルの API を SPA から呼び出すには、`src/.env` で以下の変数を変更してください:
>
> ```text
> RESOURCE_API_URL=http://localhost:8000
> ```
>
> クラウドの API に戻す場合は `python src/scripts/sync-infra-env.py` を再実行してください。

### Backend API (Autonomous Flow 使用時)

Autonomous Agent フローを使う場合は、Backend API をローカルで起動して実行することができます:

```bash
cd src && uvicorn backend_api.main:app --reload --port 8080
```

> **`.env` の変更が必要**: `sync-infra-env.py` 実行後は API の URL が Container Apps を指しています。
> ローカルの API を SPA から呼び出すには、`src/.env` で以下の変数を変更してください:
>
> ```text
> BACKEND_API_URL=http://localhost:8080
> ```
>
> クラウドの API に戻す場合は `python src/scripts/sync-infra-env.py` を再実行してください。

### Frontend SPA

別のターミナルで:

```bash
cd src/frontend && npm run dev
```

`http://localhost:5173` で Vite 開発サーバーが起動します。
ブラウザでアクセスすると、MSAL.js を使った Entra ID ログイン画面が表示されます。

---

## 利用可能な Poe タスク一覧

[Poe the Poet](https://poethepoet.naber.io/) タスクランナーで主要な操作を実行できます:

| コマンド              | 説明                                    |
| --------------------- | --------------------------------------- |
| `poe check`           | 全コンポーネントのリント・フォーマット  |
| `poe lint-backend`    | Python リント (Ruff)                    |
| `poe format-backend`  | Python フォーマット (Ruff)              |
| `poe lint-frontend`   | Frontend リント (ESLint)                |
| `poe format-frontend` | Frontend フォーマット (Prettier)        |
| `poe lint-infra`      | Terraform リント (TFLint)               |
| `poe format-infra`    | Terraform フォーマット                  |
| `poe setup`           | 開発環境セットアップ (pre-commit hooks) |

---

## 環境変数リファレンス

`src/.env` に設定される環境変数の一覧です。
ほとんどの値は `sync-infra-env.py` によって自動設定されます。

| 変数名                                       | 説明                                                    | 自動設定 |
| -------------------------------------------- | ------------------------------------------------------- | -------- |
| `AZURE_RESOURCE_GROUP`                       | Azure リソースグループ名                                | 手動     |
| `AZURE_SUBSCRIPTION_ID`                      | Azure サブスクリプション ID                             | 手動     |
| `AZURE_LOCATION`                             | Azure リージョン                                        | 手動     |
| `ENTRA_TENANT_ID`                            | Entra ID テナント ID                                    | ✅       |
| `FRONTEND_SPA_APP_URL`                       | SPA のデプロイ先 URL                                    | ✅       |
| `ENTRA_SPA_APP_CLIENT_ID`                    | SPA アプリの Client ID                                  | ✅       |
| `RESOURCE_API_URL`                           | Identity Echo API の URL                                | ✅       |
| `ENTRA_RESOURCE_API_CLIENT_ID`               | Identity Echo API の Client ID                          | ✅       |
| `ENTRA_RESOURCE_API_SCOPE`                   | Identity Echo API の delegated scope                    | ✅       |
| `ENTRA_RESOURCE_API_DEFAULT_SCOPE`           | Identity Echo API の `.default` scope                   | ✅       |
| `BACKEND_API_URL`                            | Backend API の URL                                      | ✅       |
| `ENTRA_BACKEND_API_FOUNDRY_ACCESS_CLIENT_ID` | Backend API の UAMI Client ID                           | ✅       |
| `FOUNDRY_PROJECT_ENDPOINT`                   | Foundry Project エンドポイント                          | ✅       |
| `FOUNDRY_MODEL_DEPLOYMENT_NAME`              | LLM モデルデプロイ名                                    | ✅       |
| `FOUNDRY_PROJECT_MSI`                        | Foundry Project の MSI Principal ID                     | ✅       |
| `FOUNDRY_AGENT_ACR_LOGIN_SERVER`             | ACR ログインサーバー                                    | ✅       |
| `ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID`   | Blueprint の Client ID                                  | ✅       |
| `ENTRA_AGENT_IDENTITY_CLIENT_ID`             | Agent Identity の Client ID                             | ✅       |
| `ENTRA_AGENT_ID_USER_UPN`                    | Agent User の UPN (Autonomous Agent User Flow)          | 手動     |
| `ENTRA_AGENT_ID_USER_DISPLAY_NAME`           | Agent User の表示名                                     | 手動     |
| `GRAPH_API_OPS_CLIENT_ID`                    | Graph API 操作用 Public Client ID (Entra Agent ID 設定) | ✅ \*    |

> \* `GRAPH_API_OPS_CLIENT_ID` は `labs/entra-agent-id/prereqs/` の Terraform 出力から取得します (セクション 3・4 参照)。

---

## トラブルシューティング

### Terraform apply 時のエラー

**`Cognitive Account` が既に Soft-Delete 状態で存在する**:

```bash
az cognitiveservices account purge \
  --name <account-name> \
  --resource-group <rg-name> \
  --location <location>
```

**権限不足で App Registration が作成できない**:
Entra ID で `Application.ReadWrite.All` ディレクトリ権限を持つアカウントで `az login` してください。

### ローカル起動時のエラー

**CORS エラーが発生する**:
`src/.env` の `RESOURCE_API_URL` が `http://localhost:8000` になっていることを確認してください。
Vite 開発サーバーは `src/.env` から環境変数を読み込みます。

**MSAL ログインがリダイレクトされない**:
SPA の App Registration の Redirect URI に `http://localhost:5173` が含まれていることを確認してください。
Terraform のデフォルト設定では自動的に含まれます。

---

## 次のステップ

- [再デプロイ・運用リファレンス](deployment.ja.md)
- [アーキテクチャ詳細](architecture.ja.md)
- [Entra Agent ID 概要](entra-agent-id-overview.ja.md)
