# Frontend SPA

Entra Agent ID デモアプリのフロントエンド。React + TypeScript + Vite で構築された SPA で、
MSAL.js を使った Entra ID 認証と 3 つの Agent フローの UI を提供します。

## 技術スタック

| 技術         | バージョン |
| ------------ | ---------- |
| React        | 19         |
| TypeScript   | 5.9        |
| Vite         | 8          |
| MSAL Browser | 5.6        |
| MSAL React   | 5.1        |

## ディレクトリ構成

```text
src/frontend/
├── index.html                  # エントリポイント
├── vite.config.ts              # Vite 設定 (envDir, envPrefix)
├── package.json
├── scripts/
│   └── deploy-swa.py           # Azure Static Web Apps デプロイスクリプト
├── public/                     # 静的アセット
└── src/
    ├── main.tsx                # React ルート (MsalProvider)
    ├── App.tsx                 # メインコンポーネント (タブルーティング)
    ├── authConfig.ts           # MSAL 設定・スコープ定義
    ├── api/
    │   ├── identityEchoApi.ts  # Identity Echo API クライアント
    │   ├── backendApi.ts       # Backend API クライアント (SSE 対応)
    │   └── foundryAgentApi.ts  # Foundry Agent API 直接呼び出し (Interactive OBO)
    ├── components/
    │   ├── TopBar.tsx              # ログイン/ログアウト UI
    │   ├── AutonomousChatPanel.tsx # Autonomous フロー チャット UI
    │   ├── InteractiveOboPanel.tsx # Interactive OBO フロー チャット UI
    │   ├── CallerInfo.tsx          # Identity Echo API レスポンス表示
    │   └── TokenChainSteps.tsx     # トークン交換フローの可視化
    └── utils/
        └── extractAgentToolOutput.ts  # Agent 出力パーサー
```

## UI タブ

| タブ                        | フロー          | 認証要否   | API 呼び出し経路                           |
| --------------------------- | --------------- | ---------- | ------------------------------------------ |
| **Autonomous Agent Flow**   | Autonomous      | 不要       | SPA → Backend API → Foundry → Resource API |
| **Interactive Agent (OBO)** | Interactive OBO | 要ログイン | SPA → Foundry Agent API → Resource API     |
| **No Agent Flow**           | 直接呼び出し    | 要ログイン | SPA → Resource API                         |

## 環境変数

Vite はビルド時に環境変数を埋め込みます。`vite.config.ts` で `envDir: '../'` (`src/`) を指定し、
`envPrefix` で以下のプレフィックスのみ公開します:

```typescript
envPrefix: ["ENTRA_", "RESOURCE_API_", "FOUNDRY_", "BACKEND_"];
```

| 変数                                       | 用途                             |
| ------------------------------------------ | -------------------------------- |
| `ENTRA_TENANT_ID`                          | MSAL テナント設定                |
| `ENTRA_SPA_APP_CLIENT_ID`                  | MSAL クライアント ID             |
| `ENTRA_RESOURCE_API_CLIENT_ID`             | Resource API の audience         |
| `ENTRA_RESOURCE_API_SCOPE`                 | トークン要求時のスコープ         |
| `ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID` | OBO フロー用 Blueprint Client ID |
| `RESOURCE_API_URL`                         | Identity Echo API の URL         |
| `BACKEND_API_URL`                          | Backend API の URL               |
| `FOUNDRY_PROJECT_ENDPOINT`                 | Foundry API エンドポイント       |

## MSAL 認証

- **Cache**: `sessionStorage`
- **Authority**: `https://login.microsoftonline.com/{ENTRA_TENANT_ID}`
- **トークン取得**: `acquireTokenSilent()` → フォールバックで `acquireTokenPopup()`

## ローカル開発

```bash
cd src/frontend
npm install
npm run dev
```

`http://localhost:5173` で Vite 開発サーバーが起動します。

## npm スクリプト

| コマンド         | 説明                         |
| ---------------- | ---------------------------- |
| `npm run dev`    | 開発サーバー起動 (HMR)       |
| `npm run build`  | TypeScript チェック + ビルド |
| `npm run lint`   | ESLint 実行                  |
| `npm run format` | Prettier フォーマット        |

## デプロイ

Azure Static Web Apps へのデプロイ:

```bash
python src/frontend/scripts/deploy-swa.py
```

詳細は [docs/deployment.md](../../docs/deployment.md) を参照してください。
