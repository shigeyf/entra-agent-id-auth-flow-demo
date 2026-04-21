# Entra Agent ID 概要

[English](./entra-agent-id-overview.md) | [日本語](./entra-agent-id-overview.ja.md)

Entra Agent ID は、AI エージェントに **独自の Entra ID アイデンティティ** を付与する仕組みです。
エージェントが「誰として」リソースにアクセスしたかを明確にし、監査・ガバナンスを可能にします。

> プロトコルの詳細 (シーケンス図・トークンパラメータ) は
> [Agent Identity OAuth フロー比較](agent-identity-oauth-flow-comparison.ja.md) を参照してください。

---

## なぜ Agent ID が必要か

従来の方法では、エージェントは **アプリ登録の Client Secret** や **Managed Identity** でリソースにアクセスしていました。
この場合、「どのエージェントがアクセスしたか」の識別が困難です:

| 従来の方法                 | 問題                                               |
| -------------------------- | -------------------------------------------------- |
| 共有 Client Secret         | 複数エージェントが同じ ID でアクセス、監査不能     |
| Managed Identity           | インフラ単位の ID であり、エージェント単位ではない |
| ユーザーの委任トークンのみ | エージェント自体の行動が追跡できない               |

Entra Agent ID は、エージェントごとに **固有のサービスプリンシパル** を発行し、
Entra ID の監査ログ・条件付きアクセスの対象にします。

---

## エンティティ階層

Entra Agent ID は以下の 3 層構造で管理されます:

```text
Agent Identity Blueprint (親)
├── Agent Identity A (子)
│   └── Agent User X   ← Autonomous Agent User Flow で使用
├── Agent Identity B (子)
└── Agent Identity C (子)
```

### 各エンティティの役割

| エンティティ                 | 概要                                                               | Entra ID での実体                 |
| ---------------------------- | ------------------------------------------------------------------ | --------------------------------- |
| **Agent Identity Blueprint** | エージェントのガバナンス単位。credential (FIC) を保持              | App Registration                  |
| **Agent Identity**           | 個々のエージェントインスタンスの ID。Blueprint が impersonate する | Service Principal                 |
| **Agent User**               | エージェントが impersonate するユーザーコンテキスト                | Service Principal (user 属性付き) |

- Blueprint : Agent Identity = **1 : N** (1 つの Blueprint で複数の Agent Identity を管理)
- Agent Identity : Blueprint = **N : 1** (各 Agent Identity は 1 つの Blueprint にのみ所属)
- Agent Identity : Agent User = **1 : N** (Autonomous Agent User Flow でのみ使用)

### この Demo App での対応

| エンティティ         | 作成方法                                          |
| -------------------- | ------------------------------------------------- |
| Blueprint            | Foundry Project 作成時に自動生成                  |
| Agent Identity       | Foundry Project 作成時に自動生成                  |
| Agent User           | `labs/entra-agent-id/scripts/` のスクリプトで作成 |
| Federated Credential | `labs/entra-agent-id/scripts/` のスクリプトで設定 |

---

## 3 つの OAuth フロー

Entra Agent ID は用途に応じて 3 つのフローを提供します:

### 1. Interactive (ユーザー委任型)

```text
ユーザー → SPA → Backend API → Entra ID (OBO) → Resource API
```

- ユーザーが SPA にログインし、エージェントを呼び出す
- エージェントは **ユーザーの delegated 権限** でリソースにアクセス
- 最終トークン: **delegated** (ユーザーの同意に基づくスコープ)
- トークン取得: T1 (exchange) + Tc (ユーザートークン) → OBO → TR

### 2. Autonomous Agent App (アプリ権限型)

```text
スケジューラ → Agent → Entra ID → Resource API
```

- ユーザーの介在なし
- エージェントは **自身の application 権限** でリソースにアクセス
- 最終トークン: **app-only** (管理者が事前に付与した権限)
- トークン取得: 2 段階 — T1 (exchange) → TR

### 3. Autonomous Agent User (Agent User Impersonation)

```text
スケジューラ → Agent → Entra ID (credential chaining) → Resource API
```

- ユーザーの介在なし、だが **Agent User のコンテキスト** を持つ
- エージェントは **Agent User の delegated 権限** でリソースにアクセス
- 最終トークン: **delegated** (Agent User のスコープ)
- トークン取得: 3 段階 — T1 → T2 → OBO → TR

### フロー比較

| 観点                 | Interactive            | Autonomous Agent App   | Autonomous Agent User  |
| -------------------- | ---------------------- | ---------------------- | ---------------------- |
| **ユーザー介在**     | あり (ログイン + 同意) | なし                   | なし                   |
| **最終トークン種別** | delegated              | app-only               | delegated              |
| **権限の主体**       | 人間のユーザー         | Agent Identity 自体    | Agent User             |
| **トークン段数**     | 3 (Tc + T1 → OBO → TR) | 2 (T1 → TR)            | 3 (T1 → T2 → OBO → TR) |
| **主な用途**         | 対話型チャットボット   | バッチ処理・定期タスク | ユーザー代行の自動化   |

---

## Credential: Federated Identity Credential (FIC)

Blueprint が Entra ID からトークンを取得するには **Federated Identity Credential (FIC)** が必要です。
FIC は「この Managed Identity からの assertion を信頼する」という設定です:

```text
Blueprint (App Registration)
  └── Federated Credential
        issuer: Managed Identity の OIDC issuer
        subject: Managed Identity の Client ID
```

- **本番環境**: Foundry Project の Managed Identity を issuer として設定
- **ローカル開発**: Client Secret を使用 (FIC は不要だが非推奨)

> FIC の設定手順は [Getting Started](getting-started.ja.md) のセクション 5 を参照してください。

---

## この Demo App で検証できること

| UI タブ             | フロー               | 確認ポイント                                            |
| ------------------- | -------------------- | ------------------------------------------------------- |
| **Autonomous**      | Autonomous Agent App | Agent Identity の app-only トークンで API アクセス      |
| **Interactive OBO** | Interactive          | ユーザーの delegated トークンで API アクセス (OBO 経由) |
| **No Agent**        | (参照用)             | MSAL 直接取得のトークンとの差分比較                     |

Identity Echo API は受け取ったトークンの `oid`・`azp`・`scp` を返すので、
「誰の権限でアクセスしたか」を REST レスポンスとして可視化できます。

---

## 関連ドキュメント

- [Agent Identity OAuth フロー比較](agent-identity-oauth-flow-comparison.ja.md) — 各フローのシーケンス図・トークンパラメータの詳細
- [Architecture](architecture.ja.md) — システム全体の構成図
- [Getting Started](getting-started.ja.md) — セクション 5 で Entra Agent ID のセットアップ手順を説明
