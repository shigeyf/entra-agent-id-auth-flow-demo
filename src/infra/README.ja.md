# Infrastructure (Terraform)

[English](./README.md) | [日本語](./README.ja.md)

このディレクトリには、デモアプリの Azure リソースをプロビジョニングする Terraform テンプレートが含まれています。

## クイックスタート

```bash
cd src/infra

# 変数ファイルを作成 (初回のみ)
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvars を編集して tenant_id, subscription_id 等を設定

terraform init
terraform plan
terraform apply
```

## ファイル構成の概要

| ファイル                                       | 内容                                       |
| ---------------------------------------------- | ------------------------------------------ |
| `terraform.tf`                                 | Terraform・プロバイダーのバージョン制約    |
| `providers.tf`                                 | プロバイダー設定                           |
| `_variables*.tf`                               | 入力変数 (コア, タグ, Foundry, Apps 等)    |
| `_locals*.tf`                                  | 命名規則・計算値                           |
| `data.tf`                                      | データソース                               |
| `main.rg.tf`                                   | Resource Group                             |
| `main.cognitive*.tf`                           | Foundry Resource, Project, Capability Host |
| `main.acr.tf`                                  | Azure Container Registry                   |
| `main.containerapp*.tf`                        | Container Apps 環境・アプリ                |
| `main.adapp*.tf`                               | Entra ID App Registration                  |
| `main.swa.tf`                                  | Static Web App                             |
| `main.rbac*.tf`                                | RBAC ロール割り当て                        |
| `main.loganalytics.tf` / `main.appinsights.tf` | 監視リソース                               |
| `outputs.tf`                                   | 出力値 (`sync-infra-env.py` が参照)        |

## 詳細ドキュメント

リソース構成、変数リファレンス、RBAC 一覧、命名規則、既知の注意点については:

- [Infrastructure Guide](../../docs/infrastructure.ja.md)

セットアップ手順については:

- [Getting Started](../../docs/getting-started.ja.md) — セクション 2: Terraform
