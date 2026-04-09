# Identity Echo API

Bearer トークンの caller 情報を返却する Resource API (FastAPI)。
Entra Agent ID デモの中核コンポーネントで、「誰の権限でアクセスされたか」を可視化します。

## 役割

3 つの認証フローそれぞれで Bearer トークンが異なるため、
このAPIが返す caller 情報を比較することで Entra Agent ID の動作を体験できます。

| フロー                | API が認識する caller                      | トークン種別 |
| --------------------- | ------------------------------------------ | ------------ |
| Interactive           | 人間ユーザー本人 (例: `alice@contoso.com`) | delegated    |
| Autonomous Agent App  | Agent Identity (サービスプリンシパル)      | app-only     |
| Autonomous Agent User | Agent User (例: `agentuser@contoso.com`)   | delegated    |

## API エンドポイント

| メソッド | パス            | 説明                                | 認証         |
| -------- | --------------- | ----------------------------------- | ------------ |
| GET      | `/api/resource` | Bearer トークンの caller 情報を返却 | Bearer Token |
| GET      | `/health`       | ヘルスチェック                      | なし         |

### レスポンス例 (`/api/resource`)

```json
{
  "resource": "Demo Protected Resource",
  "accessedAt": "2026-04-08T12:00:00Z",
  "caller": {
    "tokenKind": "delegated",
    "oid": "...",
    "upn": "alice@contoso.com",
    "displayName": "Alice",
    "appId": "...",
    "scopes": ["CallerIdentity.Read"],
    "roles": []
  },
  "accessToken": { "...JWT claims..." },
  "humanReadable": "alice@contoso.com の委任権限 (CallerIdentity.Read) でアクセスされました"
}
```

### トークン種別の判定

- `scp` クレームあり → `"delegated"` (委任)
- `scp` なし → `"app_only"` (アプリケーション権限)

## トークン検証

`auth/token_validator.py` で以下を検証します:

1. `Authorization: Bearer <token>` ヘッダーの存在
2. RS256 署名検証 (Microsoft Entra JWKS エンドポイントから公開鍵を取得)
3. `aud` (audience) = `ENTRA_RESOURCE_API_CLIENT_ID`
4. `iss` (issuer) = `https://login.microsoftonline.com/{TENANT_ID}/v2.0`
5. `exp` (有効期限)

## 環境変数

| 変数                           | 説明                             | 必須 |
| ------------------------------ | -------------------------------- | ---- |
| `ENTRA_TENANT_ID`              | Entra ID テナント ID             | ✅   |
| `ENTRA_RESOURCE_API_CLIENT_ID` | この API の Client ID (audience) | ✅   |
| `FRONTEND_SPA_APP_URL`         | SPA の URL (CORS 許可リスト用)   | —    |

## CORS

| オリジン                  | 用途              |
| ------------------------- | ----------------- |
| `http://localhost:3000`   | ローカル開発      |
| `http://localhost:5173`   | Vite 開発サーバー |
| `${FRONTEND_SPA_APP_URL}` | クラウド SWA      |

## ディレクトリ構成

```text
src/identity_echo_api/
├── main.py              # FastAPI アプリ初期化・CORS
├── config.py            # 環境変数・JWT 検証設定
├── auth/
│   └── token_validator.py  # Bearer トークン検証 (PyJWT + JWKS)
├── routes/
│   └── resource.py      # /api/resource エンドポイント
├── Dockerfile           # python:3.11-slim ベース
└── requirements.txt     # 依存パッケージ (PyJWT, httpx 等)
```

## ローカル起動

```bash
cd src && uvicorn identity_echo_api.main:app --reload --port 8000
```

ヘルスチェック:

```bash
curl http://localhost:8000/health
```

## デプロイ

Container Apps へのデプロイ:

```bash
python src/scripts/deploy-container-apps.py identity-echo-api
```

詳細は [docs/deployment.md](../../docs/deployment.md) を参照してください。
