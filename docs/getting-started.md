# Getting Started

[English](./getting-started.md) | [日本語](./getting-started.ja.md)

This guide walks you through setting up and deploying the Entra Agent ID demo app.

> **Note**: Deploying to Azure is required to try all three Entra Agent ID flows.
> The Foundry Hosted Agent only runs on Azure, so the demo's core features are not available with local execution alone.

## Prerequisites

### Azure Account & Permissions

| Scope              | Required Role                                                                     | Purpose                                                                                                                                                                                                |
| ------------------ | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Azure Subscription | **Owner**, or **Contributor** + **User Access Administrator**                     | Create resource groups, Foundry, Container Apps, ACR, SWA, etc. and assign RBAC roles between services (Managed Identity → ACR, Foundry, etc.)                                                         |
| Entra ID Tenant    | **Application Administrator** (or at minimum **Cloud Application Administrator**) | Create App Registrations & Enterprise Applications (Service Principals), set Application ID URIs, define API scopes, set up Entra Agent ID (Blueprint FIC, App Role grants, Agent User creation, etc.) |
| Azure CLI          | Logged in via `az login`                                                          | Used by Terraform and deployment scripts                                                                                                                                                               |

> **Entra Agent ID scripts**: Setup scripts such as `set-blueprint-fic.py` use MSAL interactive
> login to acquire Graph API delegated scopes (`AgentIdentityBlueprint.ReadWrite.All`, etc.).
> These operations are available with the Application Administrator role.
>
> **Deploying to a different tenant?** If you see `Authorization_RequestDenied` (403) errors when
> Terraform creates Service Principals or sets Identifier URIs, your account lacks the required
> Entra ID directory role in that tenant. Ask the tenant administrator to assign at least the
> **Cloud Application Administrator** role. Also verify that **"Users can register applications"**
> is set to **Yes** in the Entra admin center (Identity → Users → User settings).
>
> | Error Message                                                                         | Cause                                                                           | Required Role                             |
> | ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ----------------------------------------- |
> | `backing application of the service principal being created must in the local tenant` | Insufficient permissions to create Enterprise Applications (Service Principals) | Cloud Application Administrator or higher |
> | `Insufficient privileges to complete the operation` (on Identifier URI)               | Insufficient permissions to set Application ID URI (`api://...`)                | Cloud Application Administrator or higher |

### Development Tools

| Tool          | Version                          | Installation                                                                 |
| ------------- | -------------------------------- | ---------------------------------------------------------------------------- |
| **Terraform** | >= 1.9, < 2.0                    | [Install Terraform](https://developer.hashicorp.com/terraform/install)       |
| **Azure CLI** | Latest                           | [Install Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) |
| **Python**    | >= 3.12                          | [python.org](https://www.python.org/)                                        |
| **uv**        | Latest                           | [Install uv](https://docs.astral.sh/uv/getting-started/installation/)        |
| **Node.js**   | >= 20                            | [nodejs.org](https://nodejs.org/)                                            |
| **Docker**    | Latest (for Hosted Agent builds) | [Install Docker](https://docs.docker.com/get-docker/)                        |

> **Dev Container**: This repository includes a Dev Container configuration.
> Using VS Code with the Dev Containers extension provides an environment with all the above tools pre-installed.

---

## 1. Clone the Repository and Initial Setup

### Option A: Dev Container / GitHub Codespaces (Recommended)

Using a Dev Container pre-installs all required tools, and `postCreateCommand` automatically installs Python dependencies (`uv sync`), pre-commit hooks, and Frontend dependencies (`npm install`). **Skip all steps in this section (section 1)** and proceed to section 2.

- **GitHub Codespaces**: Launch from the repository page via "Code" → "Codespaces"
- **VS Code + Dev Container**: Install the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) and select "Reopen in Container"

### Option B: Local Environment

```bash
git clone https://github.com/<org>/microsoft-entra-agent-id.git
cd microsoft-entra-agent-id
```

#### Install Python Dependencies

```bash
uv sync
```

This installs all dependencies defined in `pyproject.toml` (FastAPI, azure-identity, azure-ai-projects, etc.) along with development tools (poethepoet, ruff).

#### Install Frontend Dependencies

```bash
cd src/frontend
npm install
cd ../..
```

---

## 2. Provision Azure Infrastructure

### 2-1. Configure Terraform Variables

```bash
cp src/infra/terraform.tfvars.example src/infra/terraform.tfvars
```

Edit `src/infra/terraform.tfvars`. The following variables **must** be set:

| Variable                        | Description                     | Example                |
| ------------------------------- | ------------------------------- | ---------------------- |
| `tenant_id`                     | Entra ID tenant ID (GUID)       | `"xxxxxxxx-xxxx-..."`  |
| `target_subscription_id`        | Azure subscription ID (GUID)    | `"xxxxxxxx-xxxx-..."`  |
| `location`                      | Azure region                    | `"eastus2"`            |
| `cognitive_project_name`        | Foundry Project name            | `"my-foundry-project"` |
| `cognitive_project_description` | Foundry Project description     | `"Demo project"`       |
| `cognitive_deployments`         | LLM model deployment definition | (see example)          |
| `container_apps`                | Container Apps definition       | (see example)          |

Default values are provided for other variables. See the comments in `.tfvars.example`.

> **Region**: The Hosted Agent in Microsoft Foundry is available in limited regions.
> Choose a region that supports Foundry Agent Service, such as `eastus2` or `swedencentral`.

### 2-2. Run Terraform (Phase 1 — Foundry bootstrap)

The full `terraform apply` is executed in **two phases**.
The SPA App Registration (created in Phase 2) references the Blueprint's `access_agent` OAuth2 scope,
which only exists after `set-blueprint-scope.py` runs in section 5. So in Phase 1 we provision the
Foundry resources first (which auto-creates the Agent Identity Blueprint), then add the scope, then
run the final apply in section 6.

```bash
cd src/infra
terraform init
terraform plan
# Phase 1: provision Foundry Resource / Project / Capability Host / Model Deployment.
# This implicitly creates the Agent Identity Blueprint via the seed-agent step.
terraform apply -target=terraform_data.seed_agent
cd ../..
```

> **Why `-target`?** The SPA App Registration (`azuread_application.client_spa`) reads the Blueprint's
> `access_agent` scope at plan time. Until the scope is added by `set-blueprint-scope.py` (section 5),
> the apply fails with `Invalid index` on an empty list. Targeting the seed agent stops Phase 1 just
> after the Blueprint is provisioned.

Terraform creates the following resources across both phases:

| Resource                             | Description                                                             |
| ------------------------------------ | ----------------------------------------------------------------------- |
| Resource Group                       | Container for all resources                                             |
| Entra ID App Registration × 2        | For SPA (`demo-client-app`) and Resource API (`demo-identity-echo-api`) |
| Foundry Resource (Cognitive Account) | Microsoft Foundry main resource (AIServices)                            |
| Foundry Project                      | Foundry project (includes Agent Identity)                               |
| Capability Host                      | Hosted Agent execution environment                                      |
| Model Deployment                     | LLM model (e.g., gpt-4.1)                                               |
| Azure Container Registry             | Container images for Agent and APIs                                     |
| Container Apps Environment + Apps    | Hosting for Backend API / Identity Echo API                             |
| Static Web App                       | Hosting for Frontend SPA                                                |
| Log Analytics + Application Insights | Monitoring & logging                                                    |
| RBAC Role Assignments                | Access permissions between services                                     |

---

## 3. Register the App for Graph API Operations

The Entra Agent ID setup scripts (sections 5 and 7) use Graph API delegated scopes
(`AgentIdentityBlueprint.ReadWrite.All`, etc.) to configure Blueprints and Agent Identities.
A Public Client App Registration for acquiring these scopes is created via Terraform.

```bash
cd labs/entra-agent-id/prereqs
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and set `tenant_id`.

```bash
terraform init
terraform plan
terraform apply
cd ../../..
```

The `agent_id_manager_client_id` output after apply will be used in `.env` in the next section.

---

## 4. Sync Terraform Outputs to `.env`

Automatically sync Terraform output values to `src/.env`:

```bash
cp src/.env.example src/.env
python src/scripts/sync-infra-env.py
```

`sync-infra-env.py` runs `terraform output` from both `src/infra` and `labs/entra-agent-id/prereqs`,
reads approximately 16 environment variables (including `GRAPH_API_OPS_CLIENT_ID` from the prereqs app),
and overwrites the corresponding lines in `src/.env`.
You don't need to fill in values manually, but the **`.env` file must exist beforehand**.
See [Environment Variable Reference](#environment-variable-reference) for the full list.

> **Note**: After Phase 1 some outputs (e.g. `ENTRA_SPA_APP_CLIENT_ID`, container app URLs) are not yet
> populated and will be skipped — that is expected. They are filled in when you re-run this script after
> Phase 2 (section 6).
>
> **Note**: `src/.env` is included in `.gitignore` and will not be committed to the repository.

---

## 5. Configure Blueprint Scope (Required Before Phase 2 Apply)

Before running the final Terraform apply, expose the `access_agent` OAuth2 scope on the
Agent Identity Blueprint. The SPA App Registration created in Phase 2 references this scope,
so it must exist beforehand.

This script sets up an App ID URI (`api://{blueprint-client-id}`) and the `access_agent` scope
on the Blueprint. The SPA later requests the `api://{blueprint}/access_agent` scope to obtain
the user token (Tc) used in the Interactive (OBO) flow.

```bash
cd src/agent
python entra-agent-id/set-blueprint-scope.py
cd ../..
```

The script:

- Acquires a Graph API token via MSAL interactive browser login (a browser window opens automatically)
- Reads `ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID` and `GRAPH_API_OPS_CLIENT_ID` from `src/.env`
- Is idempotent — skips if already configured
- Supports `--delete` to revert

---

## 6. Run Terraform (Phase 2 — Remaining resources)

Now that the Blueprint exposes the `access_agent` scope, the SPA App Registration and
all remaining resources can be created.

```bash
cd src/infra
terraform apply   # Provision the rest of the resources
cd ../..
```

> The **initial Phase 2 apply** also builds and pushes Container Apps (Backend API / Identity Echo API)
> container images to ACR and deploys them to Container Apps.

Re-run the env sync to pick up the SPA Client ID and Container App URLs created in Phase 2:

```bash
python src/scripts/sync-infra-env.py
```

---

## 7. Set Up Entra Agent ID

The Foundry Project, Agent Identity Blueprint, and Agent Identity already exist (created in section 2).
The remaining configuration enables each OAuth flow.

> **OAuth flow details**: For sequence diagrams, protocol details, and links to official documentation for each flow, see
> [Agent Identity OAuth Flow Comparison](agent-identity-oauth-flow-comparison.md).

Setup scripts are located in `src/agent/entra-agent-id/` and share the following conventions:

- Acquire Graph API tokens via MSAL interactive browser login (a browser window opens automatically)
- Read required environment variables from `src/.env`
- Idempotent — skip if already configured
- Use `--delete` option to revert settings

### 7-1. Configure Blueprint FIC (Required for All Flows)

For the Foundry Hosted Agent to acquire tokens, the Blueprint must trust the Foundry Project's
Managed Identity (MSI). A Federated Identity Credential (FIC) registers this trust relationship.

Once the FIC is registered, the Hosted Agent can use the MSI's `client_assertion` to obtain
an Exchange Token (T1) via the `client_credentials` grant. T1 serves as the starting point
for subsequent OBO exchanges and Autonomous token acquisition.

```bash
cd src/agent
python entra-agent-id/set-blueprint-fic.py
```

### 7-2. Configuration for the Interactive Agent (OBO) Flow

In the Interactive flow, the user logs in to the SPA, and the Hosted Agent accesses
the Identity Echo API with the user's delegated permissions.

> **Note**: The Blueprint scope (`access_agent`) was already configured in section 5
> as a prerequisite for the Phase 2 apply.

#### Grant Admin Consent to Agent Identity

For the Agent Identity to access the Identity Echo API on behalf of the user via OBO exchange,
tenant administrator pre-consent (Admin Consent) is required.
This script creates an OAuth2 Permission Grant with `consentType: AllPrincipals`,
allowing delegated access on behalf of **all users** in the tenant.

```bash
python entra-agent-id/grant-admin-consent-to-agent-identity.py
```

### 7-3. Configuration for the Autonomous Agent (App) Flow

In the Autonomous Agent App flow, the Agent Identity accesses the Identity Echo API
with its own application permissions, without any user involvement.

This script grants the `CallerIdentity.Read.All` App Role of the Identity Echo API
to the Agent Identity's Service Principal.
This allows the Agent Identity to call the API with an app-only token obtained via `client_credentials`.

```bash
python entra-agent-id/grant-approle-to-agent-identity.py
```

### 7-4. Configuration for the Autonomous Agent (User) Flow

In the Autonomous Agent User flow, the Agent Identity impersonates an Agent User
and accesses the Identity Echo API with that user's delegated permissions.

#### Create the Agent User

An Agent User is a special user type called `microsoft.graph.agentUser`.
Unlike regular Entra ID users, only a specific Agent Identity is allowed to impersonate it.
Manually set the following in `src/.env` beforehand:

| Variable                           | Description             | Example                           |
| ---------------------------------- | ----------------------- | --------------------------------- |
| `ENTRA_AGENT_ID_USER_UPN`          | Agent User UPN          | `"agent@contoso.onmicrosoft.com"` |
| `ENTRA_AGENT_ID_USER_DISPLAY_NAME` | Agent User display name | `"Demo Agent User"`               |

```bash
python entra-agent-id/create-agent-user.py
```

#### Grant Delegated Consent to Agent Identity

For the Agent Identity to access the Identity Echo API on behalf of the Agent User,
delegated OAuth2 pre-consent for that Agent User is required.
This script creates an OAuth2 Permission Grant with `consentType: Principal`,
allowing delegated access limited to a specific Agent User.

```bash
python entra-agent-id/grant-consent-to-agent-identity.py
```

### 7-5. Verify Configuration (Optional)

A read-only script to inspect the Blueprint configuration.
It dumps the App ID URI, exposed scopes, FIC, and Service Principal details:

```bash
python entra-agent-id/inspect-blueprint.py
```

### Script Summary

| Script                                     | Target Flow           | Description                                                                          |
| ------------------------------------------ | --------------------- | ------------------------------------------------------------------------------------ |
| `set-blueprint-fic.py`                     | All flows             | Register FIC on the Blueprint                                                        |
| `set-blueprint-scope.py`                   | All flows (prereq)    | Expose App ID URI + scope on the Blueprint (run before Phase 2 apply, see section 5) |
| `grant-admin-consent-to-agent-identity.py` | Interactive           | Grant Admin Consent (AllPrincipals)                                                  |
| `grant-approle-to-agent-identity.py`       | Autonomous Agent App  | Grant App Role to Agent Identity SP                                                  |
| `create-agent-user.py`                     | Autonomous Agent User | Create the Agent User                                                                |
| `grant-consent-to-agent-identity.py`       | Autonomous Agent User | Grant Delegated Consent (Principal)                                                  |
| `inspect-blueprint.py`                     | (Inspection)          | Dump Blueprint configuration                                                         |

---

## 8. Deploy the Hosted Agent

```bash
cd src/agent
python scripts/deploy-agent.py build push deploy --start --wait
```

This automatically performs the following steps:

1. Build the Docker image (`linux/amd64`)
2. Push to ACR
3. Create the Foundry Agent Version
4. Start the Agent and wait for startup to complete

### Verification

#### Autonomous Agent (App) Flow

Calls the Identity Echo API with the Agent Identity's own permissions (app-only) without user involvement:

```bash
python scripts/invoke-agent.py --tool call_resource_api_autonomous_app
```

#### Autonomous Agent (User) Flow

The Agent Identity impersonates the Agent User and calls the Identity Echo API with delegated permissions:

```bash
python scripts/invoke-agent.py --tool call_resource_api_autonomous_user
```

#### Interactive Agent (OBO) Flow

Opens a browser for MSAL interactive login, then calls the Identity Echo API with the user's delegated permissions:

```bash
python scripts/invoke-interactive-agent.py
```

> `invoke-agent.py` lets the LLM choose the tool by default.
> Use the `--tool` option to specify a particular flow.

---

## 9. Deploy the Frontend SPA

```bash
python src/frontend/scripts/deploy-swa.py
```

This script automatically performs:

1. Reads cloud environment variables from `src/.env`
2. Runs `npm run build` for the Vite build (embeds environment variables into the bundle)
3. Deploys the build artifacts to Azure Static Web Apps

> The deployment token is automatically retrieved from `terraform output -raw swa_deployment_token`.

---

## Local Development Server

Instructions for starting local servers when developing and debugging without using the cloud-deployed APIs.

### Identity Echo API

> **Note**: A locally running API server is not accessible from the Hosted Agent on Azure.
> The Hosted Agent calls the Identity Echo API deployed to Container Apps, so the local server
> is limited to standalone API development/debugging and testing direct calls from the SPA (No Agent Flow).

```bash
cd src && uvicorn identity_echo_api.main:app --reload --port 8000
```

Starts on `http://localhost:8000`. Health check:

```bash
curl http://localhost:8000/health
```

> **`.env` change required**: After running `sync-infra-env.py`, API URLs point to Container Apps.
> To call the local API from the SPA, change the following variable in `src/.env`:
>
> ```text
> RESOURCE_API_URL=http://localhost:8000
> ```
>
> To switch back to the cloud API, re-run `python src/scripts/sync-infra-env.py`.

### Backend API (When Using Autonomous Flow)

When using the Autonomous Agent flow, you can run and test the Backend API locally:

```bash
cd src && uvicorn backend_api.main:app --reload --port 8080
```

> **`.env` change required**: After running `sync-infra-env.py`, API URLs point to Container Apps.
> To call the local API from the SPA, change the following variable in `src/.env`:
>
> ```text
> BACKEND_API_URL=http://localhost:8080
> ```
>
> To switch back to the cloud API, re-run `python src/scripts/sync-infra-env.py`.

### Frontend SPA

In a separate terminal:

```bash
cd src/frontend && npm run dev
```

The Vite dev server starts on `http://localhost:5173`.
Open it in a browser to see the Entra ID login screen via MSAL.js.

---

## Available Poe Tasks

You can run common operations using the [Poe the Poet](https://poethepoet.naber.io/) task runner:

| Command               | Description                              |
| --------------------- | ---------------------------------------- |
| `poe check`           | Lint & format all components             |
| `poe lint-backend`    | Python lint (Ruff)                       |
| `poe format-backend`  | Python format (Ruff)                     |
| `poe lint-frontend`   | Frontend lint (ESLint)                   |
| `poe format-frontend` | Frontend format (Prettier)               |
| `poe lint-infra`      | Terraform lint (TFLint)                  |
| `poe format-infra`    | Terraform format                         |
| `poe setup`           | Dev environment setup (pre-commit hooks) |

---

## Environment Variable Reference

A list of environment variables set in `src/.env`.
Most values are automatically populated by `sync-infra-env.py`.

| Variable Name                                | Description                                                  | Auto-set |
| -------------------------------------------- | ------------------------------------------------------------ | -------- |
| `AZURE_RESOURCE_GROUP`                       | Azure resource group name                                    | Manual   |
| `AZURE_SUBSCRIPTION_ID`                      | Azure subscription ID                                        | Manual   |
| `AZURE_LOCATION`                             | Azure region                                                 | Manual   |
| `ENTRA_TENANT_ID`                            | Entra ID tenant ID                                           | Yes      |
| `FRONTEND_SPA_APP_URL`                       | SPA deployment URL                                           | Yes      |
| `ENTRA_SPA_APP_CLIENT_ID`                    | SPA app Client ID                                            | Yes      |
| `RESOURCE_API_URL`                           | Identity Echo API URL                                        | Yes      |
| `ENTRA_RESOURCE_API_CLIENT_ID`               | Identity Echo API Client ID                                  | Yes      |
| `ENTRA_RESOURCE_API_SCOPE`                   | Identity Echo API delegated scope                            | Yes      |
| `ENTRA_RESOURCE_API_DEFAULT_SCOPE`           | Identity Echo API `.default` scope                           | Yes      |
| `BACKEND_API_URL`                            | Backend API URL                                              | Yes      |
| `ENTRA_BACKEND_API_FOUNDRY_ACCESS_CLIENT_ID` | Backend API UAMI Client ID                                   | Yes      |
| `FOUNDRY_PROJECT_ENDPOINT`                   | Foundry Project endpoint                                     | Yes      |
| `FOUNDRY_MODEL_DEPLOYMENT_NAME`              | LLM model deployment name                                    | Yes      |
| `FOUNDRY_PROJECT_MSI`                        | Foundry Project MSI Principal ID                             | Yes      |
| `FOUNDRY_AGENT_ACR_LOGIN_SERVER`             | ACR login server                                             | Yes      |
| `ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID`   | Blueprint Client ID                                          | Yes      |
| `ENTRA_AGENT_IDENTITY_CLIENT_ID`             | Agent Identity Client ID                                     | Yes      |
| `ENTRA_AGENT_ID_USER_UPN`                    | Agent User UPN (for Autonomous Agent User Flow)              | Manual   |
| `ENTRA_AGENT_ID_USER_DISPLAY_NAME`           | Agent User display name                                      | Manual   |
| `GRAPH_API_OPS_CLIENT_ID`                    | Graph API operations Public Client ID (Entra Agent ID setup) | Yes \*   |

> \* `GRAPH_API_OPS_CLIENT_ID` is obtained from the Terraform output of `labs/entra-agent-id/prereqs/` (see sections 3 & 4).

---

## Troubleshooting

### Terraform Apply Errors

**`Cognitive Account` already exists in Soft-Delete state**:

```bash
az cognitiveservices account purge \
  --name <account-name> \
  --resource-group <rg-name> \
  --location <location>
```

**Insufficient permissions to create App Registration**:
Run `az login` with an account that has the `Application.ReadWrite.All` directory permission in Entra ID.

### Local Startup Errors

**CORS errors occur**:
Verify that `RESOURCE_API_URL` in `src/.env` is set to `http://localhost:8000`.
The Vite dev server reads environment variables from `src/.env`.

**MSAL login does not redirect**:
Verify that the SPA App Registration's Redirect URI includes `http://localhost:5173`.
This is automatically included in the default Terraform configuration.

---

## Next Steps

- [Deployment Guide](deployment.md)
- [Architecture Details](architecture.md)
- [Entra Agent ID Overview](entra-agent-id-overview.md)
