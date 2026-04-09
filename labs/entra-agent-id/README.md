# Microsoft Entra Agent ID

Microsoft Entra Agent ID を使った AI エージェントの ID 管理サンプルコード集です。
Microsoft Graph API (beta) を使い、Agent Identity Blueprint・Agent Identity・Agent User の作成・トークン取得を行う Python スクリプトと HTTP ワークシートを提供します。

## 概要

Microsoft Entra Agent ID は、AI エージェントに対して Microsoft Entra ID の ID 管理機能を提供する仕組みです。
エージェントの認証には大きく 3 種類のフローがあります。

| フロー                           | 概要                                                                                              |
| -------------------------------- | ------------------------------------------------------------------------------------------------- |
| **Interactive Agent**            | ユーザーが対話的にエージェントを呼び出し、ユーザーの委任権限 (delegated) でリソースにアクセスする |
| **Autonomous Agent (App Flow)**  | ユーザー介在なしに、エージェント自身の application 権限でリソースにアクセスする                   |
| **Autonomous Agent (User Flow)** | エージェントが Agent User を impersonate し、delegated 権限でリソースにアクセスする               |

詳細は [docs/agent-identity-oauth-flow-comparison.md](docs/agent-identity-oauth-flow-comparison.md) を参照してください。

## 前提条件

- Python 3.12 以上
- Microsoft Entra テナント（Microsoft Entra Agent ID プレビューが有効なこと）
- Azure CLI（`az login` でグローバル管理者または特権ロール管理者としてサインイン済みであること）

## セットアップ

### 1. 仮想環境の作成と依存パッケージのインストール

**Dev Container を使用している場合はこの手順は不要です。**
Dev Container 起動時に依存パッケージが自動インストールされます。

ローカル環境で実行する場合は、以下のコマンドを実行してください。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. 環境変数の設定

[.env.example](.env.example) をコピーして `.env` を作成し、値を設定します。

```bash
cp .env.example .env
```

| 変数                                     | 説明                                                              | 設定タイミング                                                       |
| ---------------------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------------- |
| `TENANT_ID`                              | Entra テナント ID                                                 | 手動                                                                 |
| `TENANT_NAME`                            | テナントドメイン (例: `contoso.onmicrosoft.com`)                  | 手動                                                                 |
| `MY_ID`                                  | 自分のユーザーオブジェクト ID                                     | 手動                                                                 |
| `AGENT_ID_BP_NAME`                       | Agent Identity Blueprint の表示名                                 | 手動                                                                 |
| `AGENT_ID_NAME`                          | Agent Identity の表示名                                           | 手動                                                                 |
| `AGENT_ID_USER_NAME`                     | Agent User の表示名                                               | 手動                                                                 |
| `AGENT_ID_USER_UPN`                      | Agent User の UPN                                                 | 手動                                                                 |
| `AGENT_ID_USER_OAUTH2_PERMISSION_GRANTS` | Agent User に委任するスコープ (スペース区切り)                    | 手動                                                                 |
| `AGENT_ID_BP_SECRET`                     | Blueprint のシークレット（テスト用）                              | `create-agent-id-blueprint.http` の `addPassword` 実行後に手動で設定 |
| `CLIENT_ID`                              | パブリッククライアントアプリの appId（セットアップ手順 3 で作成） | `setup-app-registration.py` 実行後に自動保存                         |
| `MS_GRAPH_SP_ID`                         | Microsoft Graph サービスプリンシパルのオブジェクト ID             | `get-approle-id.py` 実行後に自動保存                                 |
| `AGENT_ID_USER_APP_ROLE_ID`              | `AgentIdUser.ReadWrite.IdentityParentedBy` の appRole ID          | `get-approle-id.py` 実行後に自動保存                                 |
| `ACCESS_TOKEN`                           | 委任アクセストークン                                              | `get-token.py` 実行後に自動保存                                      |

### 3. パブリッククライアントアプリの登録

[src/scripts/setup-app-registration.py](src/scripts/setup-app-registration.py) を使って `az` CLI でアプリ登録を作成します。既にアプリが登録済みの場合はこの手順を省略できます。

```bash
python src/scripts/setup-app-registration.py
```

スクリプトは以下を自動実行します。

1. アプリ登録を作成（シングルテナント `AzureADMyOrg`）
2. パブリッククライアント設定（Redirect URI: `http://localhost`、Allow public client flows: 有効）
3. Microsoft Graph の委任スコープを 21 件追加
4. テナント管理者の同意を付与
5. `.env` の `CLIENT_ID` を更新

> **注意**: `admin-consent` の実行にはグローバル管理者または特権ロール管理者の権限が必要です。
> AgentIdentity 系のスコープは Microsoft Entra Agent ID プレビューが有効なテナントでのみ利用可能です。

## 使い方

### アクセストークンの取得

操作を始める前に、委任トークン (ACCESS_TOKEN) を取得します。
実行するとブラウザが開き、インタラクティブに認証を行います。

```bash
python src/scripts/get-token.py
```

取得したトークンは `.env` の `ACCESS_TOKEN` に自動保存されます。

### AppRole ID の取得 (Autonomous Agent User Flow 用)

Agent User フローで必要な AppRole ID を Microsoft Graph から取得します。

```bash
python src/scripts/get-approle-id.py
```

`MS_GRAPH_SP_ID` と `AGENT_ID_USER_APP_ROLE_ID` が `.env` に自動保存されます。

## HTTP ワークシート

[REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client) 拡張機能を使って、Microsoft Graph API を直接呼び出すワークシートを提供します。

| ファイル                                                                                     | 内容                                      |
| -------------------------------------------------------------------------------------------- | ----------------------------------------- |
| [src/api/create-agent-id-blueprint.http](src/api/create-agent-id-blueprint.http)             | Agent Identity Blueprint の作成・設定     |
| [src/api/create-agent-id.http](src/api/create-agent-id.http)                                 | Agent Identity の作成                     |
| [src/api/create-agent-id-user.http](src/api/create-agent-id-user.http)                       | Agent User の作成・AppRole 割り当て       |
| [src/api/get-autonomous-agent-id-token.http](src/api/get-autonomous-agent-id-token.http)     | Autonomous Agent (App Flow) トークン取得  |
| [src/api/get-autonomous-agent-user-token.http](src/api/get-autonomous-agent-user-token.http) | Autonomous Agent (User Flow) トークン取得 |

### 実行順序

#### Autonomous Agent (App Flow) の場合

1. `src/scripts/get-token.py` — 委任トークン取得
2. `create-agent-id-blueprint.http` — Blueprint 作成 → シークレット追加 → `.env` に `AGENT_ID_BP_SECRET` を設定
3. `create-agent-id.http` — Agent Identity 作成
4. `get-autonomous-agent-id-token.http` — 2 段階トークン取得

#### Autonomous Agent (User Flow) の場合

1. `src/scripts/get-token.py` — 委任トークン取得
2. `create-agent-id-blueprint.http` — Blueprint 作成
3. `create-agent-id.http` — Agent Identity 作成
4. `src/scripts/get-approle-id.py` — AppRole ID 取得
5. `create-agent-id-user.http` — Agent User 作成・権限付与
6. `get-autonomous-agent-user-token.http` — 3 段階トークン取得

#### Interactive Agent の場合

(作業中)

## リポジトリ構成

```text
.
├── .env.example                      # 環境変数テンプレート
├── pyproject.toml                    # プロジェクト設定
├── docs/
│   └── agent-identity-oauth-flow-comparison.md  # フロー比較ドキュメント
└── src/
    ├── get-interactive-agent-token.py      # Interactive Agent トークン取得
    ├── scripts/
    │   ├── setup-app-registration.py       # パブリッククライアントアプリ登録スクリプト
    │   ├── get-token.py                    # 委任トークン取得 (インタラクティブ認証)
    │   └── get-approle-id.py               # AppRole ID 取得
    └── api/
        ├── create-agent-id-blueprint.http  # Blueprint 作成
        ├── create-agent-id.http            # Agent Identity 作成
        ├── create-agent-id-user.http       # Agent User 作成
        ├── get-autonomous-agent-id-token.http       # Autonomous Agent App Flow トークン
        └── get-autonomous-agent-user-token.http     # Autonomous Agent User Flow トークン
```

## 開発

```bash
# 開発用依存パッケージのインストール (ruff, poe 等)
pip install -e ".[dev]"

# リントと自動フォーマット
poe check

# リントのみ
poe lint

# フォーマットのみ
poe format
```

## 参考ドキュメント

- [Microsoft Entra Agent ID の概要](https://learn.microsoft.com/en-us/entra/agent-id/overview)
- [Agent Identity Blueprint の作成](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/create-blueprint)
- [Agent Identity の作成と削除](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/create-delete-agent-identities)
- [Autonomous Agent — トークン取得](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/autonomous-agent-request-tokens)
- [Autonomous Agent — Agent User トークン取得](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/autonomous-agent-request-agent-user-tokens)
- [Interactive Agent — ユーザー認証](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/interactive-agent-authenticate-user)
- [Agent OBO フロー](https://learn.microsoft.com/en-us/entra/agent-id/identity-platform/agent-on-behalf-of-oauth-flow)

## ライセンス

MIT
