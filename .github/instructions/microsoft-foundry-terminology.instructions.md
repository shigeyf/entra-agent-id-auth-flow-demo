---
description: "Use when discussing Microsoft Foundry, Foundry classic, Azure AI Foundry, Foundry Agent Service, Hosted Agent, Capability Host, Blueprint, Agent Identity, Entra Agent ID, agent framework SDK, or any Foundry-related terminology. Prevents LLM confusion between current Microsoft Foundry and legacy Foundry (classic)."
applyTo: "{src/infra/main.cognitive*.tf,src/infra/*foundry*,src/agent/**,docs/**}"
---

# Microsoft Foundry 用語・概念ガイド

## 🚨 最重要ルール

**「Azure AI Foundry」は「Foundry (classic)」にリネームされ、Microsoft Foundry に統合された。**

公式ドキュメント "Evolution of Foundry" (learn.microsoft.com/en-us/azure/foundry/what-is-foundry) より:

| 旧称                                              | 現在の名称                                      |
| ------------------------------------------------- | ----------------------------------------------- |
| Azure AI Studio / Azure AI Foundry                | **Foundry (classic)**                           |
| Azure AI Services                                 | **Foundry Tools**                               |
| Assistants API (Agents v0.5/v1)                   | **Responses API** (Agents v2)                   |
| 複数 SDK (`azure-ai-inference`, `azure-ai-ml` 等) | 統一 SDK (`azure-ai-projects` 2.x + `OpenAI()`) |
| Hub + Azure OpenAI + Azure AI Services            | **Foundry resource** (単一、プロジェクト付き)   |

このプロジェクトが使うのは **Microsoft Foundry** である。
コード・ドキュメント・会話で「Foundry」と言った場合、**現行の Microsoft Foundry** を前提として回答すること。

---

## 1. Microsoft Foundry の全体像

Microsoft Foundry は、エージェント・モデル・ツールを統一管理グループ配下にまとめた Azure の PaaS プラットフォーム。
以下のサブサービスから構成される:

| サブサービス              | 概要                                                                                                           |
| ------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Foundry Agent Service** | AI エージェントのオーケストレーション・ホスティング (Hosted Agent, Capability Host, Blueprint, Agent Identity) |
| **Foundry Models**        | モデルカタログ、デプロイ、ファインチューニング                                                                 |
| **Foundry Tools**         | 旧 Azure AI Services (Speech, Translator, Document Intelligence 等)                                            |
| **Foundry Control Plane** | 監視、評価、ガバナンス                                                                                         |
| **Foundry IQ**            | エンタープライズ知識統合                                                                                       |
| **Foundry Local**         | ローカルデバイスでの LLM 実行                                                                                  |

### ポータルとリソースモデル

| 観点               | Microsoft Foundry (現行)                                | Foundry (classic) (旧 Azure AI Foundry)                                    |
| ------------------ | ------------------------------------------------------- | -------------------------------------------------------------------------- |
| **ポータル**       | `ai.azure.com` (New Foundry トグル ON)                  | `ai.azure.com` (classic)                                                   |
| **リソースモデル** | Foundry resource (単一) + Projects                      | Hub + Azure OpenAI + Azure AI Services (個別)                              |
| **SDK**            | `azure-ai-projects` 2.x + `OpenAI()` (1 エンドポイント) | 複数パッケージ (`azure-ai-inference`, `azure-ai-ml` 等、5+ エンドポイント) |
| **Agent API**      | Responses API (Agents v2)                               | Assistants API (Agents v0.5/v1)                                            |

---

## 2. このプロジェクト固有の情報

### Entra Agent ID に関連する Microsoft Foundry の概念

このプロジェクトは Foundry Agent Service の **Hosted Agent** と **Entra Agent ID** を使う。
これらは Microsoft Foundry 固有の概念であり、Foundry (classic) や一般的な Azure AI Services には存在しない:

- **Capability Host** (`Microsoft.CognitiveServices/accounts/capabilityHosts`) — Hosted Agent の実行環境
- **Blueprint** — Agent Identity のガバナンス単位
- **Agent Identity** — Entra ID のサービスプリンシパルとして登録されるエージェントの ID
- **Federated Credential** — Agent Identity のトークン取得に使う資格情報

### Terraform リソース構成

```text
azurerm_cognitive_account (AIServices, project_management_enabled=true)
├── azapi_resource (capabilityHosts)  ← Hosted Agent の実行環境
├── cognitive_project                 ← Microsoft Foundry Project
└── cognitive_deployment              ← LLM モデルのデプロイ
```

これらは全て `Microsoft.CognitiveServices` 配下のリソース。
Foundry (classic) の Hub ベースプロジェクト (`Microsoft.MachineLearningServices/workspaces`) ではない。

### SDK

- **Hosted Agent (Agent Framework)**: `azure-ai-agentserver-agentframework`
- **Foundry Project Client**: `azure-ai-projects` 2.x (統一 SDK)

---

## 3. よくある LLM の混同パターン

### ❌ パターン 1: 旧名称の使用

- **誤**: 「Azure AI Foundry Project を作成する」
- **正**: 現行は「Microsoft Foundry Project」。旧 Hub ベースのプロジェクトは「Foundry (classic) Project」

### ❌ パターン 2: SDK の取り違え

- **誤**: Microsoft Foundry Agent に `azure-ai-ml` や旧 `azure-ai-inference` を使う
- **正**: 統一 SDK `azure-ai-projects` 2.x + `OpenAI()` を使う
- Hosted Agent (Agent Framework) は `azure-ai-agentserver-agentframework`

### ❌ パターン 3: Capability Host / Blueprint の文脈

- Capability Host, Blueprint, Agent Identity は **Foundry Agent Service** 固有の概念
- Foundry (classic) のプロジェクトや一般的な Azure AI Services では使わない

### ❌ パターン 4: ポータル URL の混同

- 現行 Microsoft Foundry と Foundry (classic) は同じ `ai.azure.com` だが、ポータル上部の **New Foundry トグル** で切り替える
- 旧 `foundry.azure.com` や `ai.foundry.azure.com` は classic へのリダイレクト

---

## 4. 回答時のチェックリスト

Microsoft Foundry に関する質問に答える前に、以下を確認:

- [ ] 「Azure AI Foundry」を旧名称として正しく扱っているか（現在は Foundry (classic)）
- [ ] SDK 名が正しいか（統一 SDK: `azure-ai-projects` 2.x、Agent Framework: `azure-ai-agentserver-agentframework`）
- [ ] Terraform リソース種別が正しいか (`CognitiveServices` vs `MachineLearningServices`)
- [ ] Agent API が正しいか（Responses API (v2) vs Assistants API (v0.5/v1)）
- [ ] Capability Host / Blueprint / Agent Identity を正しいコンテキストで使っているか
