# Backend API

[English](./README.md) | [日本語](./README.ja.md)

SPA からの Autonomous Agent フローを仲介する FastAPI サーバーです。
SPA からの HTTP リクエストを受け取り、Foundry Hosted Agent を呼び出して結果を返します。

## 役割

```text
SPA (Frontend) → Backend API → Foundry Hosted Agent → Identity Echo API
```

- SPA から Autonomous フローのリクエストを受け付ける
- Foundry Hosted Agent を OpenAI Responses API 経由で呼び出す
- Agent の応答を JSON または SSE ストリームで SPA に返す
- Azure Managed Identity (`DefaultAzureCredential`) で Foundry に認証

## API エンドポイント

| メソッド | パス                              | 説明                              | 認証 |
| -------- | --------------------------------- | --------------------------------- | ---- |
| GET      | `/health`                         | ヘルスチェック                    | なし |
| POST     | `/api/demo/autonomous/app`        | Autonomous Agent 呼び出し         | なし |
| POST     | `/api/demo/autonomous/app/stream` | Autonomous Agent (SSE ストリーム) | なし |

### リクエスト

```json
{
  "message": "Call the resource API using the autonomous app flow.",
  "force_tool": "call_resource_api_autonomous_app"
}
```

- `message`: Agent へのプロンプト
- `force_tool` (省略可): 使用する Tool を指定

### レスポンス

- `/autonomous/app`: JSON (`{"tool_output": {...}, "agent_message": "..."}`)
- `/autonomous/app/stream`: Server-Sent Events (OpenAI Responses API フォーマット)

## 環境変数

| 変数                       | 説明                           | 必須 |
| -------------------------- | ------------------------------ | ---- |
| `FOUNDRY_PROJECT_ENDPOINT` | Foundry Project エンドポイント | ✅   |
| `ENTRA_TENANT_ID`          | Entra ID テナント ID           | ✅   |
| `FRONTEND_SPA_APP_URL`     | SPA の URL (CORS 許可リスト用) | —    |

## CORS

| オリジン                  | 用途              |
| ------------------------- | ----------------- |
| `http://localhost:5173`   | Vite 開発サーバー |
| `http://localhost:4173`   | Vite プレビュー   |
| `${FRONTEND_SPA_APP_URL}` | クラウド SWA      |

## ディレクトリ構成

```text
src/backend_api/
├── main.py              # FastAPI アプリ初期化・CORS
├── config.py            # 環境変数読み込み
├── foundry_client.py    # Foundry Agent 呼び出しロジック
├── routes/
│   └── call_foundry_agent.py  # エンドポイントハンドラ
├── Dockerfile           # python:3.11-slim ベース
└── requirements.txt     # 依存パッケージ
```

## ローカル起動

```bash
cd src && uvicorn backend_api.main:app --reload --port 8080
```

> Foundry に接続するため、`az login` 済みである必要があります
> (`DefaultAzureCredential` がローカルの Azure CLI 資格情報を使用します)。

## デプロイ

Container Apps へのデプロイ:

```bash
python src/scripts/deploy-container-apps.py backend-api
```

詳細は [docs/deployment.ja.md](../../docs/deployment.ja.md) を参照してください。
