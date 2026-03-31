# Copilot Workspace Instructions

## プロジェクト概要

Entra Agent ID デモアプリ。Microsoft Foundry の Hosted Agent と Entra Agent ID を使い、
Interactive / Autonomous App / Autonomous User の 3 フローで「誰の権限でリソース API にアクセスしたか」を
可視化するデモンストレーション。

## ⚠️ 重要: Microsoft Foundry の用語

**このプロジェクトで「Foundry」と言った場合、現行の Microsoft Foundry を指す。**

Microsoft は「Azure AI Foundry」を「**Foundry (classic)**」にリネームし、Microsoft Foundry に統合した。
公式の "Evolution of Foundry" テーブル (learn.microsoft.com/en-us/azure/foundry/what-is-foundry) に基づき、以下を厳守:

| 旧称                                   | 現在の名称                                      |
| -------------------------------------- | ----------------------------------------------- |
| Azure AI Studio / Azure AI Foundry     | **Foundry (classic)**                           |
| Azure AI Services                      | **Foundry Tools**                               |
| Assistants API (Agents v0.5/v1)        | **Responses API** (Agents v2)                   |
| 複数 SDK + 5+ エンドポイント           | 統一 SDK (`azure-ai-projects` 2.x + `OpenAI()`) |
| Hub + Azure OpenAI + Azure AI Services | **Foundry resource** (単一 + Projects)          |

**このプロジェクト固有の情報**:

- Foundry Agent Service の **Hosted Agent** + **Entra Agent ID** を使用
- Agent Framework SDK: `azure-ai-agentserver-agentframework`
- インフラ: `azurerm_cognitive_account` (AIServices) + `azapi_resource` (capabilityHosts)
- Capability Host, Blueprint, Agent Identity は Foundry Agent Service 固有の概念

## 技術スタック

- **Frontend**: React + TypeScript + Vite + MSAL.js
- **Identity Echo API**: FastAPI (Python) + Bearer Token 検証
- **Agent**: Foundry Hosted Agent (Python, `azure-ai-agentserver-agentframework`)
- **Infrastructure**: Terraform (azurerm + azapi)
- **認証**: Microsoft Entra ID, MSAL, Entra Agent ID
