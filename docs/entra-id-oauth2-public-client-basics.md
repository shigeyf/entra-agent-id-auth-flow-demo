# Entra ID OAuth2 フロー基礎 — Public Client (SPA) 編

> このドキュメントは、Microsoft Entra ID における OAuth2 / OpenID Connect の基本的な考え方を整理したうえで、
> このリポジトリの SPA と Resource API の構成に当てはめて理解しやすくすることを目的としています。
> トークンの claim 値や発行条件には、アプリ種別、要求するリソース、access token のバージョン、テナント設定などにより差異があります。
> ここでは理解に必要な範囲に絞って概要を説明し、詳細は文末の Microsoft 公式ドキュメントを参照してください。

## 1. 全体像: なぜ 2 つのアプリ登録が必要か

OAuth2 では **「アクセスする側（クライアント）」** と **「アクセスされる側（リソース）」** を分離する。
Entra ID ではそれぞれを **App Registration（アプリ登録）** として作成する。

```text
┌──────────────────────┐         ┌─────────────────────┐              ┌──────────────────────┐
│  ユーザー(ブラウザ)  │         │   Entra ID          │              │  Resource API        │
│                      │         │   (認可サーバー)    │              │  (リソースサーバー)  │
└──────────────────────┘         └─────────────────────┘              └──────────────────────┘
            │                               │                                    │
            │  ① ログイン                  │                                    │
            │──────────────────────────────▶│                                    │
            │  ② アクセストークン返却      │                                    │
            │◀──────────────────────────────│                                    │
            │                               │                                    │
            │  ③ Bearer トークン付きで API 呼び出し                             │
            │───────────────────────────────────────────────────────────────────▶│
            │                               │                                    │ ④ トークン検証 (aud, iss, 署名)
            │                               │                                    │   ※ ローカルで実行
            │  ⑤ レスポンス返却                                                 │
            │◀───────────────────────────────────────────────────────────────────│
```

> **④ について**: Resource API は Entra ID の JWKS エンドポイントから公開鍵を事前取得・キャッシュしており、トークン検証はリソースサーバー側でローカルに実行される。リクエストの都度 Entra ID に問い合わせるわけではない。

| 役割             | このプロジェクトでの名前 | 説明                                           |
| ---------------- | ------------------------ | ---------------------------------------------- |
| 認可サーバー     | Entra ID (テナント)      | トークン発行・検証鍵の公開                     |
| クライアント     | `demo-client-app` (SPA)  | ユーザーをログインさせ、アクセストークンを取得 |
| リソースサーバー | `demo-identity-echo-api` | トークンを検証し、保護されたデータを返す       |

---

## 2. リソース API 側のアプリ登録

リソース API のアプリ登録は **「保護したい API を Entra ID に宣言する」** 行為。

### 2-1. App ID URI

```text
api://<application_id>
```

- Resource API を識別するための識別子
- クライアントがスコープを要求するときの接頭辞として使われる（例: `api://<API_ID>/<scope_name>`）
- access token の `aud` および `iss` claim の値は、リソース API のアプリマニフェストの `accessTokenAcceptedVersion` 設定により異なる:

  | `accessTokenAcceptedVersion` | `aud`                          | `iss`                                                |
  | ---------------------------- | ------------------------------ | ---------------------------------------------------- |
  | `null`（既定）または `1`     | App ID URI（`api://...`）      | `https://sts.windows.net/<TENANT_ID>/`               |
  | `2`                          | Application (client) ID (GUID) | `https://login.microsoftonline.com/<TENANT_ID>/v2.0` |

  詳細は [Access tokens — Token formats](https://learn.microsoft.com/entra/identity-platform/access-tokens#token-formats) を参照

- このサンプルでは Terraform の `azuread_application` リソースで `requested_access_token_version = 2` を設定しているため、`aud` は `<RESOURCE_API_CLIENT_ID>`（GUID）、`iss` は `https://login.microsoftonline.com/<TENANT_ID>/v2.0` となる

### 2-2. Delegated Permission（委任スコープ）

- ユーザーがサインインした状態で、ユーザーの代理としてアクセスする権限
- クライアントがトークン取得時に `api://<API_ID>/<scope_name>` として要求
- トークンの `scp` クレームにスコープ名が含まれる

### 2-3. Application Permission（アプリロール）

- ユーザーなしでアプリ自身の権限でアクセスする場合（デーモン、バックエンド向け）
- トークンの `roles` クレームに含まれる
- このサンプルの SPA 構成では扱わない

### 2-4. Service Principal

- **App Registration** = アプリの「設計図」（グローバル定義）
- **Service Principal** = テナントにおけるアプリの「実体」（Enterprise Application）
- Azure Portal 上では **Enterprise Applications**（エンタープライズ アプリケーション）ブレードに表示される
- Service Principal がないと、そのテナントで権限の付与や同意ができない

---

## 3. クライアント SPA 側のアプリ登録

### 3-1. プラットフォーム設定 (SPA)

- **SPA** プラットフォームを選択すると、Entra ID は **Authorization Code Flow with PKCE** を使用
- SPA はシークレットを安全に保持できないため、`client_secret` の代わりに **PKCE** で保護
- `redirect_uris` は認証後にトークンを受け取る URL（事前登録済みの値と完全一致が必要）

### 3-2. API Permission の要求

- 「この SPA は〈リソース API〉の〈スコープ〉を使います」という宣言
- アプリマニフェスト（および本リポジトリの Terraform 定義 `required_resource_access` ブロック）で permission の種類を指定する:
  - `type = "Scope"` → Delegated permission（ユーザー委任）
  - `type = "Role"` → Application permission

### 3-3. 管理者同意 (Admin Consent)

- 通常、ユーザーが初回アクセス時に同意画面で許可する
- 事前に Admin Consent を付与すると、ユーザーに同意画面が出ない
- エンタープライズ環境でよく使うパターン

---

## 4. OAuth2 Authorization Code Flow with PKCE

SPA が Entra ID からアクセストークンを取得する全フロー。

```text
  ブラウザ (SPA)                                    Entra ID                    Resource API
      │                                                │                              │
      │ ① loginPopup() 呼び出し                       │                              │
      │───────────────────────────────────────────────▶│                              │
      │   GET /authorize                               │                              │
      │   ?client_id=<SPA_CLIENT_ID>                   │                              │
      │   &response_type=code                          │                              │
      │   &scope=api://<API_ID>/<scope>                │                              │
      │     openid profile offline_access              │                              │
      │   &redirect_uri=http://localhost:5173/         │                              │
      │   &code_challenge=<PKCE_HASH>                  │                              │
      │   &code_challenge_method=S256                  │                              │
      │   &state=<CSRF対策ランダム値>                  │                              │
      │                                                │                              │
      │ ② サインイン画面表示                          │                              │
      │◀───────────────────────────────────────────────│                              │
      │                                                │                              │
      │ ③ ユーザーが資格情報入力                      │                              │
      │───────────────────────────────────────────────▶│                              │
      │                                                │                              │
      │ ④ authorization code 返却                     │                              │
      │◀───────────────────────────────────────────────│                              │
      │   redirect_uri?code=<AUTH_CODE>                │                              │
      │                                                │                              │
      │ ⑤ code → token 交換                           │                              │
      │───────────────────────────────────────────────▶│                              │
      │   POST /token                                  │                              │
      │   grant_type=authorization_code                │                              │
      │   code=<AUTH_CODE>                             │                              │
      │   code_verifier=<PKCE_PLAIN>                   │  ← PKCE 検証                 │
      │   client_id=<SPA_CLIENT_ID>                    │                              │
      │                                                │                              │
      │ ⑥ トークン返却                                │                              │
      │◀───────────────────────────────────────────────│                              │
      │   { access_token, id_token,                    │                              │
      │     refresh_token }                            │                              │
      │                                                │                              │
      │ ⑦ API 呼び出し                                │                              │
      │   Authorization: Bearer <access_token>         │                              │
      │──────────────────────────────────────────────────────────────────────────────▶│
      │                                                │                              │ ⑧ トークン検証
      │                                                │                              │   (Resource API 側でローカル実行)
      │                                                │                              │   - JWKS で署名検証
      │                                                │                              │   - aud 検証 (※)
      │                                                │                              │   - iss 検証
      │                                                │                              │   - exp > now
      │ ⑨ レスポンス返却                              │                              │
      │◀──────────────────────────────────────────────────────────────────────────────│
```

> **※ ⑧ aud 検証について**: `aud` の値はトークンバージョン等により異なる（セクション 2-1 参照）。このサンプルでは `accessTokenAcceptedVersion = 2` のため、`<RESOURCE_API_CLIENT_ID>`（GUID）を期待値として検証している。
>
> **⑥ の補足**: `refresh_token` は `offline_access` スコープが要求された場合に返却される。MSAL.js は既定でこのスコープを含めるため、通常は明示的な指定なしで取得できる。

---

## 5. `/authorize` と `/token` の認証情報

### 5-1. `/authorize` — ユーザーを認証する場

`/authorize` は **ブラウザリダイレクト (GET)** で呼ばれる。**クライアント自身の認証は行わない**。

| パラメータ              | 必須         | 説明                                                                                                     |
| ----------------------- | ------------ | -------------------------------------------------------------------------------------------------------- |
| `response_type`         | 必須         | `code`（Authorization Code Flow）                                                                        |
| `client_id`             | 必須         | クライアント識別子。**認証ではなく識別のみ**                                                             |
| `redirect_uri`          | 条件付き必須 | 事前登録済みの値と完全一致が必要                                                                         |
| `scope`                 | 必須         | 要求するスコープ。OIDC では `openid` が必須。Entra ID v2.0 エンドポイントでは scope パラメータ自体が必須 |
| `state`                 | 推奨(必須級) | CSRF 対策のランダム値                                                                                    |
| `code_challenge`        | PKCE 時必須  | `code_verifier` の SHA-256 (Base64URL)                                                                   |
| `code_challenge_method` | PKCE 時必須  | `S256`                                                                                                   |
| `nonce`                 | OIDC 時推奨  | ID トークンのリプレイ攻撃対策                                                                            |

URL はブラウザのアドレスバー経由で送られるため **シークレットを含めてはいけない**。
`client_id` は申告のみ。保護は以下のレイヤーで担保される:

1. **redirect_uri** の完全一致検証 → 認可コードの送信先を制限
2. **state** → CSRF 攻撃を防止
3. **code_challenge (PKCE)** → 認可コードの横取りを防止
4. **ユーザー自身の認証** → Entra ID がユーザーに資格情報を要求

### 5-2. `/token` — クライアントを認証する場

`/token` は **POST (バックチャネル)** で呼ばれる。クライアントの種類で認証方法が異なる。

#### Public Client (SPA) — PKCE で保護

Public Client (SPA) では `client_secret` を安全に保持できないため、Confidential Client のようなクライアント認証は行わない。
代わりに Authorization Code Flow with PKCE を用い、`/authorize` で発行された認可コードを、同じ実行主体が `/token` で交換していることを検証する。
つまり PKCE は、secret の代替となる完全なクライアント認証ではなく、認可コード横取り対策として機能する。

```text
POST /token
  grant_type=authorization_code
  &code=<認可コード>
  &code_verifier=<PKCE_PLAIN>
  &client_id=<SPA_CLIENT_ID>
  &redirect_uri=http://localhost:5173/
```

`client_secret` がないため、`code_verifier` により「認可コードを要求した実行主体」と「認可コードを交換する実行主体」が対応していることを確認する:

```text
/authorize 時:
  ① code_verifier = ランダム文字列 (43-128文字) を生成
  ② code_challenge = BASE64URL(SHA256(code_verifier)) を計算
  ③ code_challenge を /authorize に送信
     → Entra ID が認可コードと紐付けて記録

/token 時:
  ④ code_verifier をそのまま送信
  ⑤ Entra ID が SHA256(code_verifier) == 記録済み code_challenge を検証
  → 一致 = `/authorize` 時に提示した code_challenge に対応する code_verifier を持つ実行主体であることを示せる
```

#### Confidential Client（参考: Web サーバー、デーモン）

| 方式                  | 送信方法                                          |
| --------------------- | ------------------------------------------------- |
| `client_secret_post`  | ボディに `client_secret` を含める                 |
| `client_secret_basic` | `Authorization: Basic base64(id:secret)` ヘッダー |
| `private_key_jwt`     | 秘密鍵で署名した JWT を `client_assertion` に送信 |

#### 比較表

|                  | `/authorize`       | `/token` (Public/SPA)                   | `/token` (Confidential)                          |
| ---------------- | ------------------ | --------------------------------------- | ------------------------------------------------ |
| HTTP メソッド    | GET (リダイレクト) | POST (バックチャネル)                   | POST (バックチャネル)                            |
| クライアント認証 | なし (識別のみ)    | PKCE により認可コード交換の正当性を確認 | `client_secret`、証明書、`client_assertion` など |
| ユーザー認証     | あり               | なし                                    | なし                                             |
| client_secret    | 絶対に含めない     | 使わない                                | 場合による（secret / 証明書 / assertion）        |

---

## 6. スコープと audience の関係 — 1 トークン = 1 audience

### 6-1. 原則

Entra ID v2.0 では **1つのアクセストークンに含められる audience は 1つだけ**。

異なるリソースのスコープを混ぜるとエラーになる:

```text
// NG: 2つの異なるリソースのスコープを同時に要求
scope=api://<MY_API>/CallerIdentity.Read https://graph.microsoft.com/User.Read
→ AADSTS エラー（Entra ID は 1 リクエストで複数リソースのスコープを受け付けない）
```

> 詳細: [Scopes and permissions — The .default scope](https://learn.microsoft.com/entra/identity-platform/scopes-oidc#the-default-scope)

### 6-2. `openid` / `profile` はなぜ混ぜられるか

```text
scope=api://<API_ID>/CallerIdentity.Read openid profile
```

`openid`、`profile`、`email`、`offline_access` は OpenID Connect 系のスコープであり、Resource API の delegated scope とは役割が異なる。
`openid` は ID トークンの発行要求、`profile` と `email` は主に ID トークンに含めるユーザー属性に影響し、`offline_access` は refresh token の発行要求に使われる。
一方で、Resource API の scope は access token の対象リソースと権限を決める。
そのため、`api://<API_ID>/<scope>` と `openid profile offline_access` を同時に要求しても、access token の audience は 1 つの Resource API に対して発行される。

| スコープ                             | 影響するトークン         | 役割                                                             |
| ------------------------------------ | ------------------------ | ---------------------------------------------------------------- |
| `api://<API_ID>/CallerIdentity.Read` | **アクセストークン**     | API の aud と scp を決定                                         |
| `openid`                             | **ID トークン**          | ID トークン発行の要求 / `/userinfo` エンドポイントへのアクセス権 |
| `profile`                            | **ID トークン**          | name, preferred_username 等のクレーム要求                        |
| `email`                              | **ID トークン**          | email クレーム                                                   |
| `offline_access`                     | **リフレッシュトークン** | リフレッシュトークンの発行                                       |

なお、MSAL.js (Browser) は `openid` `profile` `offline_access` を既定で自動的にスコープに追加する。詳細は [MSAL.js — Initializing client applications](https://learn.microsoft.com/entra/identity-platform/msal-js-initializing-client-applications) を参照。

1 回の `/authorize` → `/token` のレスポンス:

```json
{
  "access_token": "aud=<RESOURCE_API_CLIENT_ID>, scp=CallerIdentity.Read",
  "id_token": "name, preferred_username, email 等 (openid/profile の効果)",
  "refresh_token": "(offline_access 指定時)"
}
```

**アクセストークンの audience は 1 つだけ**。`openid` / `profile` は別のトークン (ID トークン) の中身を制御しているに過ぎない。

### 6-3. 複数の API にアクセスしたい場合

`/authorize` (ログイン) は **1 回**。`/token` はリソースごとに呼ぶ。

```text
① loginPopup({ scopes: ["api://<MY_API>/CallerIdentity.Read"] })
   → /authorize + /token
   → access_token (aud=MY_API) + id_token + refresh_token

② acquireTokenSilent({ scopes: ["https://graph.microsoft.com/User.Read"] })
   → /token (grant_type=refresh_token)
   → access_token (aud=Graph)          ← 新しい audience のトークン
```

ユーザーのインタラクションは 1 回。以降は MSAL がバックグラウンドで `/token` を呼ぶ。

> **補足**: `acquireTokenSilent` は、キャッシュミス時にまず refresh token による `/token` 呼び出しを試みる。キャッシュに refresh token がない場合（ページリロード直後など）は hidden iframe を使った silent SSO にフォールバックする。上記は簡略化した流れであり、詳細は [MSAL.js — Token acquisition](https://learn.microsoft.com/entra/identity-platform/msal-js-sso) を参照。

---

## 7. リフレッシュトークンの仕組み

### 7-1. `/token` の grant_type による違い

| タイミング | grant_type           | 認証情報                        |
| ---------- | -------------------- | ------------------------------- |
| 初回       | `authorization_code` | `code` + `code_verifier` (PKCE) |
| 2 回目以降 | `refresh_token`      | `refresh_token` のみ            |

初回の code 交換:

```text
POST /token
  grant_type=authorization_code
  &code=<認可コード>
  &code_verifier=<PKCE>
  &client_id=<SPA_CLIENT_ID>
  &redirect_uri=...
```

2 回目以降 (acquireTokenSilent):

```text
POST /token
  grant_type=refresh_token
  &refresh_token=0.AVYAq1K8...       ← これが認証の代わり
  &client_id=<SPA_CLIENT_ID>
  &scope=api://<API_ID>/<scope>
```

### 7-2. リフレッシュトークンの特性

| 特性            | 内容                                                                                       |
| --------------- | ------------------------------------------------------------------------------------------ |
| 形式            | **Opaque 文字列** (JWT ではない)                                                           |
| 紐付け先        | client_id + user に紐付く                                                                  |
| audience 紐付け | **なし** — 許可済みの別 resource に対する access_token の取得にも使える                    |
| SPA 有効期間    | **24 時間** ※                                                                              |
| ローテーション  | 利用時に新しいものが返ることがある。クライアントは新しいものを保持し、古いものは破棄すべき |

> **※ なぜ SPA のリフレッシュトークンは 24 時間固定なのか**
> ブラウザ環境（SPA）はシークレットを安全に保管できず、XSS 等によるトークン窃取のリスクが相対的に高い。
> これを軽減するセキュリティ上の仕様として、Entra ID では **SPA 向けリフレッシュトークンの有効期間は最大 24 時間に制限されており、テナントのカスタムポリシー等でも延長できない（変更不可のハードリミット）**。
> 参考: [Microsoft ID プラットフォームでの更新トークン](https://learn.microsoft.com/ja-jp/entra/identity-platform/refresh-tokens#token-timeouts)

### 7-3. リフレッシュトークンが audience に紐付かない理由

refresh token は特定の resource 用ではなく、ユーザーとクライアントの認証済みセッションを表す。
そのため、クライアントが既に同意を得ている別 resource の scope に対して、新しい access token を取得するために使える。
「どの API にアクセスしてよいか」は認可サーバーが `/token` リクエスト時に毎回判断する。

判断の基準:

1. **アプリ登録**: クライアントの `required_resource_access` にスコープが宣言されているか
2. **同意**: ユーザーまたは管理者がそのスコープに同意しているか

どちらかが欠けると、refresh token があっても `/token` は失敗する（例: `AADSTS65001`）。

### 7-4. acquireTokenSilent の全体フロー

```text
時刻    操作                /authorize    /token           認証情報
─────────────────────────────────────────────────────────────────────────────────────────
T=0     loginPopup()        GET ✓         POST ✓          code + code_verifier (PKCE)
        → access_token (既定: 約1時間), refresh_token (24h), id_token を取得

T=30m   acquireTokenSilent  —             —               キャッシュヒット
        → キャッシュから即返却 (通信なし)

T=61m   acquireTokenSilent  —             POST ✓          refresh_token
        → access_token 期限切れ → refresh_token で新トークン取得

T=90m   acquireTokenSilent  —             POST ✓          refresh_token (ローテ済み新版)
        → 同上

T=24h   acquireTokenSilent  —             POST ✗ (失敗)   refresh_token 期限切れ
        → InteractionRequiredAuthError → 再ログインが必要
```

---

## 8. MSAL API と Entra ID エンドポイントの対応

| MSAL API               | 内部通信 (Entra ID エンドポイント)                               | 条件・状態                                                 |
| ---------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------- |
| `loginPopup()`         | `/authorize` → `/token` (`grant_type=authorization_code` + PKCE) | 初回ログイン（常にユーザー操作あり）                       |
| `acquireTokenSilent()` | 通信なし (ローカルキャッシュから即返却)                          | キャッシュに有効な access_token がある場合                 |
| `acquireTokenSilent()` | `/token` (`grant_type=refresh_token`) をバックグラウンドで実行   | キャッシュにない or 期限切れ（refresh_token が有効な場合） |
| `acquireTokenSilent()` | hidden iframe による silent SSO                                  | キャッシュに refresh_token がない場合のフォールバック      |
| `acquireTokenPopup()`  | `/authorize` → `/token` (`grant_type=authorization_code` + PKCE) | `acquireTokenSilent` が失敗した場合のフォールバック        |

`acquireTokenPopup()` が必要になるケース:

- refresh_token が期限切れ (SPA: 24 時間)
- 管理者がリフレッシュトークンを失効させた
- 新しいスコープにユーザー同意が必要（Admin Consent がない場合）
- Conditional Access ポリシーで再認証が要求された

---

## 9. アクセストークンの中身（Delegated / Application）

> **注意**: 以下のサンプルは `accessTokenAcceptedVersion = 2`（v2 トークン）の場合の例。`null` または `1`（v1 トークン）に変更した場合、`aud` や `iss` の形式が異なる（セクション 2-1 参照）。

### Delegated (ユーザー委任) — SPA 経由でユーザーがログイン

```json
{
  "aud": "<RESOURCE_API_CLIENT_ID>",
  "iss": "https://login.microsoftonline.com/<TENANT_ID>/v2.0",
  "azp": "<SPA_CLIENT_ID>",
  "oid": "ユーザーのオブジェクト ID",
  "upn": "user@contoso.com", // オプショナル claim（シングルテナントでは通常含まれる）
  "name": "表示名",
  "scp": "CallerIdentity.Read",
  "idtyp": "user",
  "exp": 1234567890
}
```

### Application (アプリ権限) — デーモン等がクライアント資格情報で取得

```json
{
  "aud": "<RESOURCE_API_CLIENT_ID>",
  "iss": "https://login.microsoftonline.com/<TENANT_ID>/v2.0",
  "oid": "サービスプリンシパルのオブジェクト ID",
  "azp": "<DAEMON_CLIENT_ID>",
  "roles": ["CallerIdentity.Read.All"],
  "idtyp": "app",
  "exp": 1234567890
}
```

判定方法:

- **確実な方法**: `idtyp` claim を確認する。`"user"` なら delegated token、`"app"` なら application token。ただし `idtyp` はオプショナルな claim であり、v1 トークンなど条件によって含まれない場合がある（参考: [Access tokens — Token types](https://learn.microsoft.com/entra/identity-platform/access-tokens#token-types)）
- **実用的な方法**: `scp` claim があれば delegated token、`scp` がなく `roles` claim に権限が入っていれば application token
- **注意**: `roles` claim は delegated token に現れる場合もあるため、`roles` の有無だけで application token と断定しない

> 詳細: [Access tokens — Token types](https://learn.microsoft.com/entra/identity-platform/access-tokens#token-types)

---

## 10. まとめ

| 概念             | Entra ID での設定                      | 役割                                                                                    |
| ---------------- | -------------------------------------- | --------------------------------------------------------------------------------------- |
| 認可サーバー     | Entra ID 自体 (テナント)               | トークン発行・検証鍵の公開                                                              |
| クライアント     | SPA アプリ登録                         | ユーザーをログインさせ、アクセストークンを取得                                          |
| リソースサーバー | API アプリ登録                         | トークンを検証し、保護されたデータを返す                                                |
| スコープ         | `oauth2_permission_scope`              | API が公開する権限の粒度                                                                |
| 同意             | Admin Consent / ユーザー同意           | クライアントがスコープを使用する許可                                                    |
| PKCE             | MSAL.js が自動処理                     | SPA にシークレットがなくてもコード交換を安全に行う                                      |
| audience         | access token が対象とする Resource API | 1 トークン = 1 audience。複数 API は別トークン                                          |
| refresh_token    | Entra ID が発行 (opaque)               | user + client に紐づく長寿命トークン。resource 非依存で新しい access token の取得に使う |

---

## 11. 詳細な公式ドキュメント

- [Access tokens in the Microsoft identity platform](https://learn.microsoft.com/entra/identity-platform/access-tokens)
- [Refresh tokens in the Microsoft identity platform](https://learn.microsoft.com/entra/identity-platform/refresh-tokens)
- [Scopes and permissions in the Microsoft identity platform](https://learn.microsoft.com/entra/identity-platform/scopes-oidc)
- [Microsoft identity platform and OAuth 2.0 authorization code flow](https://learn.microsoft.com/entra/identity-platform/v2-oauth2-auth-code-flow)
- [Application and service principal objects in Microsoft Entra ID](https://learn.microsoft.com/entra/identity-platform/app-objects-and-service-principals)
- [MSAL.js で SSO を実現する方法](https://learn.microsoft.com/entra/identity-platform/msal-js-sso)
