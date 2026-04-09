# Infrastructure Guide

Terraform によるインフラ構成の読解ガイドです。
`src/infra/` ディレクトリの全体像、リソース構成、変数の設定方法を説明します。

## Terraform バージョン・プロバイダー

| 要件      | バージョン     |
| --------- | -------------- |
| Terraform | >= 1.9, < 2.0  |
| azurerm   | >= 4.37, < 5.0 |
| azapi     | >= 2.5, < 3.0  |
| azuread   | >= 3.0, < 4.0  |

- **azurerm**: Azure リソースの大半を管理
- **azapi**: Capability Host・Foundry Connection など azurerm 未サポートのリソースに使用
- **azuread**: Entra ID App Registration・Service Principal の作成

---

## ファイル構成

```text
src/infra/
├── terraform.tf                          # Terraform・プロバイダーのバージョン制約
├── providers.tf                          # プロバイダー設定
├── _locals.tf                            # 命名規則・Container Apps 環境変数の計算
├── _locals.naming.tf                     # リソース名生成 (SHA256 + ランダム文字列)
├── _variables.tf                         # コア変数 (tenant_id, location 等)
├── _variables.tags.tf                    # 組織タグ (owner, cost_center 等)
├── _variables.foundry.tf                 # Foundry 関連変数 (Project, Model 等)
├── _variables.containerapp.tf            # Container Apps 定義
├── _variables.adapp.client-spa.tf        # SPA App Registration 変数
├── _variables.adapp.identity-echo-api.tf # Identity Echo API App Registration 変数
├── _variables.swa.tf                     # Static Web App 変数
├── data.tf                               # データソース (現在のクライアント情報等)
│
├── main.rg.tf                            # Resource Group
├── main.acr.tf                           # Azure Container Registry
├── main.cognitive.tf                     # Foundry Resource (Cognitive Account)
├── main.cognitive.project.tf             # Foundry Project
├── main.cognitive.capabilityhost.tf      # Capability Host (Hosted Agent 実行環境)
├── main.cognitive.deployment.tf          # LLM モデルデプロイ
├── main.cognitive.connection.appinsights.tf # Foundry ↔ App Insights 接続
├── main.adapp.client-spa.tf              # SPA App Registration
├── main.adapp.identity-echo-api.tf       # Identity Echo API App Registration
├── main.containerapp.tf                  # Container Apps 環境・UAMI
├── main.containerapp.apps.tf             # Container Apps 定義 + ACR ビルド
├── main.swa.tf                           # Static Web App
├── main.loganalytics.tf                  # Log Analytics Workspace
├── main.appinsights.tf                   # Application Insights
├── main.rbac.definitions.tf              # RBAC ロール定義 (locals)
├── main.rbac.services.tf                 # サービス間 RBAC 割り当て
├── main.rbac.users.tf                    # ユーザー・グループ RBAC 割り当て
│
├── outputs.tf                            # 出力値 (sync-infra-env.py が参照)
├── terraform.tfvars.example              # 変数設定のサンプル
└── terraform.tfvars                      # 実際の変数設定 (git 管理外)
```

---

## Azure リソース構成

### 全体像

```text
Resource Group
├── Foundry Resource (Cognitive Account / AIServices)
│   ├── Foundry Project (System-Assigned MI)
│   │   └── Agent Identity Blueprint + Agent Identity (自動作成)
│   ├── Capability Host (Hosted Agent 実行環境)
│   ├── Model Deployment (gpt-4.1 等)
│   └── Connection (App Insights)
├── Azure Container Registry (Basic)
├── Container Apps Environment
│   ├── Identity Echo API (Container App)
│   └── Backend API (Container App)
├── Static Web App (Free)
├── Log Analytics Workspace
├── Application Insights
├── Entra ID App Registration × 2
│   ├── SPA (demo-client-app)
│   └── Identity Echo API (demo-identity-echo-api)
└── RBAC Role Assignments
```

### Foundry リソースの階層

Foundry 固有のリソースは全て `Microsoft.CognitiveServices` 配下です:

```text
azurerm_cognitive_account (kind: AIServices)
├── azurerm_cognitive_account_project     ← Foundry Project (MI が Agent Identity を保持)
├── azapi_resource (capabilityHosts)      ← Hosted Agent の実行環境
├── azurerm_cognitive_deployment (×N)     ← LLM モデルのデプロイ
└── azapi_resource (connections)          ← App Insights との接続
```

> Foundry Project を作成すると、Agent Identity Blueprint と Agent Identity が自動的にプロビジョニングされます。
> Terraform で直接管理する必要はありませんが、`outputs.tf` から Client ID を取得します。

---

## 必要な変数

### 必須変数

| 変数                            | 説明                        | 例                    |
| ------------------------------- | --------------------------- | --------------------- |
| `tenant_id`                     | Entra ID テナント ID        | `"xxxxxxxx-xxxx-..."` |
| `target_subscription_id`        | Azure サブスクリプション ID | `"xxxxxxxx-xxxx-..."` |
| `location`                      | Azure リージョン            | `"eastus2"`           |
| `cognitive_project_name`        | Foundry Project 名          | `"my-project"`        |
| `cognitive_project_description` | Foundry Project の説明      | `"Demo project"`      |
| `cognitive_deployments`         | LLM モデルデプロイ定義      | (tfvars.example 参照) |
| `container_apps`                | Container Apps 定義         | (tfvars.example 参照) |

### 主要なオプション変数

| 変数                               | デフォルト           | 説明                                  |
| ---------------------------------- | -------------------- | ------------------------------------- |
| `naming_suffix`                    | `["foundry", "poc"]` | リソース名のプレフィックス            |
| `env`                              | `"dev"`              | 環境識別子                            |
| `is_production`                    | `false`              | 削除保護・Soft-Delete パージの制御    |
| `swa_location`                     | `"eastus2"`          | SWA のリージョン (メインとは別指定可) |
| `ai_project_developers_group_name` | `""`                 | 開発者グループ (RBAC 割り当て)        |
| `ai_project_users_group_name`      | `""`                 | ユーザーグループ (RBAC 割り当て)      |
| `enable_cognitive_local_auth`      | `false`              | API キー認証の有効化 (非推奨)         |

---

## RBAC ロール割り当て

### サービス間

| 割り当て元               | 割り当て先        | ロール                                        | 用途                                    |
| ------------------------ | ----------------- | --------------------------------------------- | --------------------------------------- |
| Foundry Project MI       | Cognitive Account | Cognitive Services User                       | Hosted Agent が LLM を呼び出し          |
| Foundry Project MI       | ACR               | AcrPull, Container Registry Repository Reader | Hosted Agent がイメージを Pull          |
| Container Apps 共有 UAMI | ACR               | AcrPull                                       | Container Apps がイメージを Pull        |
| Backend API 専用 UAMI    | Cognitive Account | Cognitive Services User                       | Backend API が Foundry Agent を呼び出し |

### ユーザー・グループ

| 割り当て元         | ロール             | 条件                     |
| ------------------ | ------------------ | ------------------------ |
| デプロイ実行者     | Azure AI Owner     | 常に (Account + Project) |
| Developer グループ | Azure AI Developer | グループ名が設定時のみ   |
| User グループ      | Azure AI User      | グループ名が設定時のみ   |

---

## 命名規則

リソース名は `_locals.naming.tf` で自動生成されます。
SHA256 ハッシュとランダム文字列を使い、グローバル一意性を確保します:

| パターン     | フォーマット                                 | 用途例                       |
| ------------ | -------------------------------------------- | ---------------------------- |
| longName     | `{prefix}-{project}-{env}-{region}-{hash6}`  | Resource Group, App Insights |
| simpleName   | `{prefix}-{project}-{env}-{region}`          | Foundry Project              |
| alphanumName | `{prefix}{proj5}{env3}{hash14}` (英数字のみ) | ACR                          |

---

## Terraform 出力値

`outputs.tf` で約 30 の値が出力されます。主要な出力:

| 出力                                  | 説明                           | `.env` 変数                                |
| ------------------------------------- | ------------------------------ | ------------------------------------------ |
| `tenant_id`                           | テナント ID                    | `ENTRA_TENANT_ID`                          |
| `client_app_client_id`                | SPA の Client ID               | `ENTRA_SPA_APP_CLIENT_ID`                  |
| `resource_api_client_id`              | Identity Echo API の Client ID | `ENTRA_RESOURCE_API_CLIENT_ID`             |
| `resource_api_scope`                  | delegated scope                | `ENTRA_RESOURCE_API_SCOPE`                 |
| `foundry_project_endpoint`            | Foundry エンドポイント         | `FOUNDRY_PROJECT_ENDPOINT`                 |
| `foundry_agent_identity_id`           | Agent Identity Client ID       | `ENTRA_AGENT_IDENTITY_CLIENT_ID`           |
| `foundry_agent_identity_blueprint_id` | Blueprint Client ID            | `ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID` |
| `acr_login_server`                    | ACR ログインサーバー           | `FOUNDRY_AGENT_ACR_LOGIN_SERVER`           |
| `resource_api_url`                    | Identity Echo API URL          | `RESOURCE_API_URL`                         |
| `backend_api_url`                     | Backend API URL                | `BACKEND_API_URL`                          |
| `swa_deployment_token`                | SWA デプロイトークン (機密)    | (deploy-swa.py が直接参照)                 |

> `sync-infra-env.py` が `terraform output -json` を実行し、これらの値を `src/.env` に自動同期します。

---

## 初回 apply 時の動作

`terraform apply` は以下の順序でリソースを作成します:

1. Resource Group
2. Entra ID App Registration × 2
3. Foundry Resource → Project → Capability Host → Model Deployment
4. ACR → `az acr build` で Container イメージをビルド (null_resource)
5. Container Apps Environment → RBAC 伝播待機 (60 秒) → Container Apps
6. Static Web App
7. RBAC Role Assignments (サービス間 + ユーザー)

> **注意**: `null_resource.acr_build` により、初回 `terraform apply` で Container Apps のイメージまでビルド・デプロイされます。

---

## 既知の注意点

### Capability Host の削除

Capability Host は Azure API で `DELETE` がサポートされていません。
`terraform destroy` 前に state から手動で削除する必要があります:

```bash
terraform state rm 'azapi_resource.capabilityhost'
```

### Cognitive Account の Soft-Delete

削除済みの Cognitive Account が Soft-Delete 状態で残っている場合、同名の再作成に失敗します:

```bash
az cognitiveservices account purge \
  --name <account-name> \
  --resource-group <rg-name> \
  --location <location>
```

### SWA リージョン

Static Web App は利用可能なリージョンが限定されています。
`swa_location` は `location` (Foundry リソースのリージョン) とは別に指定できます。

---

## 関連ドキュメント

- [Getting Started](getting-started.md) — セクション 2 で Terraform の実行手順を説明
- [Architecture](architecture.md) — リソース構成の全体像
- [再デプロイ・運用リファレンス](deployment.md) — Terraform 変更後の再デプロイ手順
