# Deployment Guide — 再デプロイ・運用リファレンス

このガイドでは、コード変更後の再デプロイ手順と、各コンポーネントのデプロイ詳細を説明します。

> **初回セットアップ**: 環境構築からデプロイまでの一本道の手順は
> [Getting Started](getting-started.md) を参照してください。このドキュメントは
> Getting Started のセクション 1〜7 が完了済みの環境を前提としています。

## 前提条件

- [Getting Started](getting-started.md) のセクション 1〜7 が完了していること
- Azure CLI でログイン済み (`az login`)
- Docker が利用可能 (Hosted Agent ビルド時)

---

## デプロイパイプライン概要

```text
terraform apply  ──→  sync-infra-env.py  ──┬──→  deploy-container-apps.py
(インフラ変更時)      (.env 再同期)        │     (Backend API / Identity Echo API)
                                           │
                                           ├──→  deploy-swa.py
                                           │     (Frontend SPA)
                                           │
                                           └──→  deploy-agent.py
                                                  (Hosted Agent)
```

> Container Apps・SWA・Hosted Agent のデプロイは互いに独立しており、並行実行が可能です。

---

## 更新時のクイックリファレンス

コード変更後は、変更したコンポーネントのみ再デプロイします:

| 変更箇所                   | 再デプロイコマンド                                                                    |
| -------------------------- | ------------------------------------------------------------------------------------- |
| Identity Echo API のコード | `python src/scripts/deploy-container-apps.py identity-echo-api`                       |
| Backend API のコード       | `python src/scripts/deploy-container-apps.py backend-api`                             |
| Frontend SPA のコード      | `python src/frontend/scripts/deploy-swa.py`                                           |
| Hosted Agent のコード      | `cd src/agent && python scripts/deploy-agent.py build push deploy --start --wait`     |
| Terraform 定義             | `cd src/infra && terraform apply && cd ../.. && python src/scripts/sync-infra-env.py` |
| 環境変数の変更             | `python src/scripts/sync-infra-env.py` → 影響コンポーネントを再デプロイ               |

---

## Container Apps (Backend API / Identity Echo API)

### 一括デプロイ

```bash
python src/scripts/deploy-container-apps.py
```

### 個別デプロイ

```bash
# Identity Echo API のみ
python src/scripts/deploy-container-apps.py identity-echo-api

# Backend API のみ
python src/scripts/deploy-container-apps.py backend-api
```

### 処理内容

1. `src/.env` から ACR 名・リソースグループなどの値を読み込み
2. `az acr build` でコンテナイメージをビルド・ACR にプッシュ
3. `az containerapp update` で Container App を最新イメージに更新

> **注意**: 初回の `terraform apply` で Container Apps は自動デプロイされるため、
> このスクリプトはコード変更後の **再デプロイ** で使用します。

### デプロイの確認

```bash
# Identity Echo API
curl https://<identity-echo-api-fqdn>/health

# Backend API
curl https://<backend-api-fqdn>/health
```

FQDN は `cd src/infra && terraform output container_app_urls` で確認できます。

---

## Frontend SPA (Static Web Apps)

### デプロイ

```bash
python src/frontend/scripts/deploy-swa.py
```

### ビルドをスキップして再デプロイのみ

```bash
python src/frontend/scripts/deploy-swa.py --skip-build
```

### 処理内容

1. `src/.env` からクラウド用の環境変数 (API URL、Entra ID 設定) を読み込み
2. `src/.env.production` を一時生成 (クラウド URL をビルド時に埋め込み)
3. `npm run build` で Vite ビルド (TypeScript コンパイル + バンドル)
4. `terraform output` から SWA デプロイメントトークンを取得
5. `swa deploy` で `dist/` を Static Web Apps にデプロイ

### Vite の環境変数

Vite はビルド時に環境変数を埋め込みます。`deploy-swa.py` は `src/.env` の以下の値を
`.env.production` 経由で Vite に渡します:

| 環境変数                       | 用途                             |
| ------------------------------ | -------------------------------- |
| `ENTRA_TENANT_ID`              | MSAL テナント設定                |
| `ENTRA_SPA_APP_CLIENT_ID`      | MSAL クライアント ID             |
| `ENTRA_RESOURCE_API_CLIENT_ID` | リソース API の audience         |
| `ENTRA_RESOURCE_API_SCOPE`     | トークン要求時のスコープ         |
| `RESOURCE_API_URL`             | Identity Echo API のクラウド URL |
| `BACKEND_API_URL`              | Backend API のクラウド URL       |

> **ローカルとクラウドの違い**: ローカル開発では `src/.env` を直接読みますが、
> クラウドデプロイでは `.env.production` にクラウド URL を書き込んでから Vite ビルドを行います。

### デプロイの確認

```bash
cd src/infra && terraform output frontend_spa_app_url
```

出力された URL にブラウザでアクセスして SPA が表示されることを確認します。

---

## Hosted Agent

### デプロイ

```bash
cd src/agent
python scripts/deploy-agent.py build push deploy --start --wait
```

### 処理内容

| ステップ   | 内容                                  | 詳細                                                      |
| ---------- | ------------------------------------- | --------------------------------------------------------- |
| **build**  | `docker build --platform linux/amd64` | Agent ランタイムのコンテナイメージをビルド                |
| **push**   | `az acr login` → `docker push`        | ACR にイメージをプッシュ                                  |
| **deploy** | `create_version()`                    | `agent.yaml` に基づき Foundry Agent Version を作成        |
| **start**  | `az cognitiveservices agent start`    | Hosted Agent を起動し、Responses API 経由で利用可能にする |

### 個別ステップの実行

```bash
cd src/agent

# ビルドとプッシュのみ (デプロイ・起動なし)
python scripts/deploy-agent.py build push

# デプロイと起動のみ (既にイメージが ACR にある場合)
python scripts/deploy-agent.py deploy --start --wait
```

> **Agent Version の冪等性**: `create_version` API は冪等です。定義 (イメージ URI、環境変数等) が
> 前回と同一の場合、新しいバージョンは作成されず既存バージョンが返されます。
> スクリプトはこれを検知し、`delete-deployment` → `start` でコンテナイメージを入れ替えます。

### 動作確認

```bash
cd src/agent
python scripts/invoke-agent.py --tool call_resource_api_autonomous_app
```

---

## トラブルシューティング

### CORS エラー

SPA からの API 呼び出しで CORS エラーが発生する場合:

1. `src/.env` の `FRONTEND_SPA_APP_URL` が正しい値であること
2. Container Apps の再デプロイで環境変数が反映されていること

```bash
# Container Apps を再デプロイして環境変数を反映
python src/scripts/deploy-container-apps.py
```

### ACR ビルドエラー

**`unauthorized: authentication required`**:

```bash
az acr login --name <acr-name>
```

**ビルドタイムアウト**:
ACR ビルドのデフォルトタイムアウトは 600 秒です。ネットワーク状況によっては延長が必要な場合があります。

### Hosted Agent が起動しない

1. Agent のステータスを確認:

   ```bash
   az cognitiveservices agent show \
     --account-name <cognitive-account-name> \
     --project-name <project-name> \
     --resource-group <resource-group>
   ```

2. Capability Host が正しくプロビジョニングされているか確認

3. ACR のイメージが `linux/amd64` プラットフォームでビルドされていることを確認

### SWA デプロイ時の `swa_deployment_token` エラー

```text
ERROR: could not read swa_deployment_token from terraform output
```

Terraform の state が `src/infra` にあり、SWA リソースが作成済みであることを確認してください:

```bash
cd src/infra && terraform output swa_deployment_token
```

---

## 関連ドキュメント

- [Getting Started](getting-started.md) — 初回セットアップ・ローカル起動
- [Architecture](architecture.md) — コンポーネント構成詳細
- [Hosted Agent の詳細](../src/agent/README.md) — Agent のアーキテクチャ・デプロイライフサイクル
