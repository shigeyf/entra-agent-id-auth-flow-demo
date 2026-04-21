# Entra Agent ID Demo App — Foundry Hosted Agent

[English](./README.md) | [日本語](./README.ja.md)

A demo application that visualizes the three authentication flows of Microsoft Entra Agent ID.

Using [Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/what-is-foundry) Hosted Agent and [Entra Agent ID](https://learn.microsoft.com/en-us/entra/agent-id/), this app lets you compare in real time **"whose permissions were used to access the resource API."**

## What This Demo Shows

A single agent (Agent Identity) operates across three authentication flows, visualizing **who the resource API (Identity Echo API) perceives as the caller**.

| Scenario                  | Flow               | Caller as Seen by the API                             | Token Type |
| ------------------------- | ------------------ | ----------------------------------------------------- | ---------- |
| **Interactive Agent**     | OBO (On-Behalf-Of) | The human user themselves (e.g., `alice@contoso.com`) | delegated  |
| **Autonomous Agent App**  | client_credentials | The Agent Identity itself (service principal)         | app-only   |
| **Autonomous Agent User** | user_fic           | An Agent User (e.g., `agentuser@contoso.com`)         | delegated  |

This embodies the core value of Entra Agent ID — **a single agent can switch between different permission contexts depending on the calling context**.

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│  Frontend SPA (React + MSAL.js)                             │
│  Azure Static Web Apps                                      │
└──────────┬──────────────────────────────────────────────────┘
           │ (Simulates a system trigger)  │ Interactive Flow
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

## Tech Stack

| Component         | Technology                                                             |
| ----------------- | ---------------------------------------------------------------------- |
| Frontend          | React 19 + TypeScript + Vite + MSAL.js                                 |
| Backend API       | FastAPI (Python) — Mediates Autonomous flows from the SPA              |
| Identity Echo API | FastAPI (Python) — Returns caller information from the Bearer token    |
| Agent             | Microsoft Foundry Hosted Agent (`azure-ai-agentserver-agentframework`) |
| Infrastructure    | Terraform (azurerm + azapi + azuread)                                  |
| Authentication    | Microsoft Entra ID, MSAL, Entra Agent ID                               |
| CI/CD             | Deployment automation via Python scripts                               |

## Project Structure

| Directory                                                 | Description                                                      |
| --------------------------------------------------------- | ---------------------------------------------------------------- |
| [src/frontend/](src/frontend/README.md)                   | React SPA (Vite + MSAL.js)                                       |
| [src/backend_api/](src/backend_api/README.md)             | Backend API (FastAPI) — Mediates Foundry Agent invocations       |
| [src/identity_echo_api/](src/identity_echo_api/README.md) | Identity Echo API (FastAPI) — Token validation & caller info     |
| [src/agent/](src/agent/README.md)                         | Foundry Hosted Agent (runtime + deploy + entra-agent-id scripts) |
| [src/infra/](src/infra/README.md)                         | Terraform (Azure resource definitions)                           |
| src/scripts/                                              | Deployment automation scripts                                    |
| docs/                                                     | Architecture & OAuth flow documentation                          |
| labs/                                                     | Entra Agent ID hands-on lab (manual flow verification)           |

## Quick Start

### Prerequisites

#### Azure / Entra ID Permissions

| Scope              | Required Role                                                                     | Purpose                                                                                                                                                                                                |
| ------------------ | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Azure Subscription | **Owner**, or **Contributor** + **User Access Administrator**                     | Create resource groups, Foundry, Container Apps, ACR, SWA, etc. and assign RBAC roles between services (Managed Identity → ACR, Foundry, etc.)                                                         |
| Entra ID Tenant    | **Application Administrator** (or at minimum **Cloud Application Administrator**) | Create App Registrations & Enterprise Applications (Service Principals), set Application ID URIs, define API scopes, set up Entra Agent ID (Blueprint FIC, App Role grants, Agent User creation, etc.) |

> **Deploying to a different tenant?** If you see `Authorization_RequestDenied` (403) errors when
> Terraform creates Service Principals or sets Identifier URIs, your account lacks the required
> Entra ID directory role in that tenant. Ask the tenant administrator to assign at least the
> **Cloud Application Administrator** role. Also verify that **"Users can register applications"**
> is set to **Yes** in the Entra admin center (Identity → Users → User settings).

#### Option A: Dev Container / GitHub Codespaces (Recommended)

Using a Dev Container provides a ready-to-use environment with all required tools (Terraform, Azure CLI, Node.js, Python, uv, Docker) pre-installed. No additional installation is needed.

- **GitHub Codespaces**: Launch from the repository page via "Code" → "Codespaces"
- **VS Code + Dev Container**: Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) and select "Reopen in Container"

> The Dev Container automatically runs `uv sync` and `poe setup` via `postCreateCommand`, so Python dependencies and pre-commit hooks are already configured on startup.

#### Option B: Local Environment

Manually install the following tools:

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.9
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) (already logged in)
- [Node.js](https://nodejs.org/) >= 20
- [Python](https://www.python.org/) >= 3.12 + [uv](https://docs.astral.sh/uv/)
- [Docker](https://docs.docker.com/get-docker/) (for building the Hosted Agent)

### Setup Steps

> **Note**: Deploying to Azure is required to try all three Entra Agent ID flows.
> The Foundry Hosted Agent only runs on Azure, so the demo's core features are not available with local execution alone.

1. Clone the repository and install dependencies
2. Provision infrastructure with Terraform (Container Apps are also deployed at this stage)
3. Register the app for Graph API operations (Prereqs Terraform)
4. Sync Terraform outputs to `.env`
5. Set up Entra Agent ID (Blueprint FIC configuration, etc.)
6. Deploy the Hosted Agent
7. Deploy the Frontend SPA

For detailed instructions, see [docs/getting-started.md](docs/getting-started.md).
For redeployment and operations, see [docs/deployment.md](docs/deployment.md).

## Documentation

| Document                                                                             | Description                                              |
| ------------------------------------------------------------------------------------ | -------------------------------------------------------- |
| [Getting Started](docs/getting-started.md)                                           | Complete guide: prerequisites, setup, and launch         |
| [Deployment](docs/deployment.md)                                                     | Redeployment & operations reference                      |
| [Architecture](docs/architecture.md)                                                 | Component layout & data flow details                     |
| [Infrastructure](docs/infrastructure.md)                                             | Terraform infrastructure & variable guide                |
| [Entra Agent ID Overview](docs/entra-agent-id-overview.md)                           | Entra Agent ID concepts & three-flow overview            |
| [Agent Identity OAuth Flow Comparison](docs/agent-identity-oauth-flow-comparison.md) | Protocol details & sequence diagrams for all three flows |

## License

[MIT](LICENSE)
