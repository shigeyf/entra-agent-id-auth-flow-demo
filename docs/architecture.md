# Architecture

[English](./architecture.md) | [日本語](./architecture.ja.md)

An architectural overview of the Entra Agent ID demo app.

## Component Layout

```text
┌─────────────────────────────────────────────────────────────┐
│  Frontend SPA (React + MSAL.js)                             │
│  Azure Static Web Apps                                      │
└──────────┬──────────────────────────────────────────────────┘
           │ (Simulates a system triiger)  │ Interactive Flow
           ▼                               │
┌─────────────────────┐                    │
│  Backend API        │                    │
│  (FastAPI)          │                    │
│  Container Apps     │                    │
└──────────┬──────────┘                    │
           │ Autonomous Flow               │
           ▼                               ▼
┌────────────────────────────────────────────────────────────┐
│  Foundry Agent Service (Hosted Agent, Responses API)       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Token Exchange (MI Token → TR)                       │  │
│  │  Autonomous (App):  Obtains TR with Agent's own      │  │
│  │                     permissions                      │  │
│  │  Autonomous (User): Obtains TR with Agent User's     │  │
│  │                     delegated permissions            │  │
│  │  Interactive:       Obtains TR via OBO using the     │  │
│  │                     user's Tc                        │  │
│  └──────────────────────┬───────────────────────────────┘  │
└─────────────────────────┼──────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────┐
│  Identity Echo API (FastAPI)                               │
│  Container Apps                                            │
│  → Returns caller information from the Bearer token        │
└────────────────────────────────────────────────────────────┘
```

## Component List

| Component                | Technology               | Hosting               | Role                                                                   |
| ------------------------ | ------------------------ | --------------------- | ---------------------------------------------------------------------- |
| **Frontend SPA**         | React 19 + MSAL.js       | Azure Static Web Apps | UI, user authentication, flow switching                                |
| **Backend API**          | FastAPI (Python)         | Azure Container Apps  | Mediates Autonomous flows (authenticates to Foundry via MSI)           |
| **Identity Echo API**    | FastAPI (Python)         | Azure Container Apps  | Returns caller information from the Bearer token (Resource API)        |
| **Foundry Hosted Agent** | Agent Framework (Python) | Foundry Agent Service | Token acquisition (Entra Agent ID), API calls, LLM formatting          |
| **Microsoft Entra ID**   | —                        | Azure                 | Authentication & authorization (Blueprint, Agent Identity, Agent User) |

---

## Data Flow

### Differences in Call Paths

Who calls the Foundry Agent API differs by flow:

| Aspect                         | Interactive                      | Autonomous (App / User)                 |
| ------------------------------ | -------------------------------- | --------------------------------------- |
| Entity calling the Foundry API | The user themselves (MSAL token) | Backend API (Managed Identity)          |
| Role of the Frontend           | Auth + direct Foundry call       | Sends trigger and displays results only |
| Presence of user token (Tc)    | Yes (input for OBO)              | No                                      |

### Interactive Flow

```text
User → Frontend (MSAL login)
     → Foundry Agent API (Bearer = user's Entra ID token)
       ├─ Passes Tc via message payload
       ├─ Obtains T1 (Project MSI)
       ├─ OBO exchange (T1 + Tc → TR, sub = user themselves)
       └─ Identity Echo API (Bearer TR)
          → caller: alice@contoso.com (delegated)
```

### Autonomous Agent App Flow

```text
User → Frontend (no authentication required)
     → Backend API (POST /api/demo/autonomous/app)
       → Foundry Agent API (Bearer = MSI token)
         ├─ Obtains T1 (Project MSI)
         ├─ client_credentials (T1 → TR, sub = Agent Identity)
         └─ Identity Echo API (Bearer TR)
            → caller: Agent Identity SP (app-only)
```

### Autonomous Agent User Flow

```text
User → Frontend (no authentication required)
     → Backend API (POST /api/demo/autonomous/app)
       → Foundry Agent API (Bearer = MSI token)
         ├─ Obtains T1 (Project MSI)
         ├─ client_credentials (T1 → T2)
         ├─ user_fic (T2 → TR, sub = Agent User)
         └─ Identity Echo API (Bearer TR)
            → caller: agentuser@contoso.com (delegated)
```

---

## Authentication Flow Overview

The subject of the token that reaches the Identity Echo API differs across the three flows:

| Flow                  | Token Exchange                  | Subject of TR                        | Token Type |
| --------------------- | ------------------------------- | ------------------------------------ | ---------- |
| Interactive           | T1 + Tc → TR (OBO / jwt-bearer) | Human user (`alice@contoso.com`)     | delegated  |
| Autonomous Agent App  | T1 → TR (client_credentials)    | Agent Identity (service principal)   | app-only   |
| Autonomous Agent User | T1 → T2 → TR (user_fic)         | Agent User (`agentuser@contoso.com`) | delegated  |

> For detailed sequence diagrams and protocol specifications, see
> [Agent Identity OAuth Flow Comparison](agent-identity-oauth-flow-comparison.md).

### Entra ID Entities

| Entity                             | Type                        | Role                                                                 |
| ---------------------------------- | --------------------------- | -------------------------------------------------------------------- |
| Agent Identity Blueprint           | App Registration            | Parent of Agent Identity. Holds FIC, scopes, and Application Consent |
| Agent Identity                     | Service Principal           | Derived from Blueprint. The entity that acquires tokens              |
| Agent User                         | `microsoft.graph.agentUser` | A special user that only a specific Agent Identity can impersonate   |
| SPA App Registration               | App Registration            | For Frontend SPA MSAL authentication                                 |
| Identity Echo API App Registration | App Registration            | Defines audience, scopes, and App Roles for the Resource API         |

---

## Azure Resource Layout

Terraform (`src/infra/`) provisions the following resources:

| Resource                             | Description                                                     |
| ------------------------------------ | --------------------------------------------------------------- |
| Resource Group                       | Container for all resources                                     |
| Entra ID App Registration × 2        | For SPA and Identity Echo API                                   |
| Foundry Resource (Cognitive Account) | Microsoft Foundry main resource (AIServices)                    |
| Foundry Project                      | Automatically creates Agent Identity Blueprint + Agent Identity |
| Capability Host                      | Hosted Agent execution environment                              |
| Model Deployment                     | LLM model (e.g., gpt-4.1)                                       |
| Azure Container Registry             | Container images for Agent and APIs                             |
| Container Apps Environment + Apps    | Backend API / Identity Echo API                                 |
| Static Web App                       | Frontend SPA                                                    |
| Log Analytics + Application Insights | Monitoring & logging                                            |
| RBAC Role Assignments                | Access permissions between services                             |

---

## Project Structure

```text
src/
├── frontend/          # React SPA (Vite + MSAL.js)
├── backend_api/       # Backend API (FastAPI) — Mediates Foundry Agent invocations
├── identity_echo_api/ # Identity Echo API (FastAPI) — Token validation & caller info
├── agent/             # Foundry Hosted Agent (runtime + deploy scripts)
│   ├── runtime/       #   Agent runtime code (main.py, tools/)
│   ├── entra-agent-id/#   Entra Agent ID setup scripts
│   └── scripts/       #   Deploy & invocation scripts
├── infra/             # Terraform (Azure resource definitions)
└── scripts/           # Deployment automation scripts
docs/                  # Architecture & OAuth flow documentation
labs/                  # Entra Agent ID hands-on lab
```

See each component's README for details:

- [Frontend SPA](../src/frontend/README.md)
- [Backend API](../src/backend_api/README.md)
- [Identity Echo API](../src/identity_echo_api/README.md)
- [Hosted Agent](../src/agent/README.md)

---

## Related Documentation

- [Getting Started](getting-started.md) — Step-by-step guide for environment setup and deployment
- [Agent Identity OAuth Flow Comparison](agent-identity-oauth-flow-comparison.md) — Sequence diagrams & protocol details
- [Deployment Guide](deployment.md) — Per-component redeployment procedures
