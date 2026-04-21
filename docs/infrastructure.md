# Infrastructure Guide

[English](./infrastructure.md) | [日本語](./infrastructure.ja.md)

A guide to understanding the Terraform infrastructure layout.
This covers the overall structure, resource layout, and variable configuration in the `src/infra/` directory.

## Terraform Versions & Providers

| Requirement | Version        |
| ----------- | -------------- |
| Terraform   | >= 1.9, < 2.0  |
| azurerm     | >= 4.37, < 5.0 |
| azapi       | >= 2.5, < 3.0  |
| azuread     | >= 3.0, < 4.0  |

- **azurerm**: Manages the majority of Azure resources
- **azapi**: Used for resources not yet supported by azurerm, such as Capability Host and Foundry Connection
- **azuread**: Creates Entra ID App Registrations and Service Principals

---

## File Structure

```text
src/infra/
├── terraform.tf                          # Terraform & provider version constraints
├── providers.tf                          # Provider configuration
├── _locals.tf                            # Naming conventions & Container Apps env var computation
├── _locals.naming.tf                     # Resource name generation (SHA256 + random strings)
├── _variables.tf                         # Core variables (tenant_id, location, etc.)
├── _variables.tags.tf                    # Organization tags (owner, cost_center, etc.)
├── _variables.foundry.tf                 # Foundry-related variables (Project, Model, etc.)
├── _variables.containerapp.tf            # Container Apps definitions
├── _variables.adapp.client-spa.tf        # SPA App Registration variables
├── _variables.adapp.identity-echo-api.tf # Identity Echo API App Registration variables
├── _variables.swa.tf                     # Static Web App variables
├── data.tf                               # Data sources (current client info, etc.)
│
├── main.rg.tf                            # Resource Group
├── main.acr.tf                           # Azure Container Registry
├── main.cognitive.tf                     # Foundry Resource (Cognitive Account)
├── main.cognitive.project.tf             # Foundry Project
├── main.cognitive.capabilityhost.tf      # Capability Host (Hosted Agent execution environment)
├── main.cognitive.deployment.tf          # LLM model deployment
├── main.cognitive.connection.appinsights.tf # Foundry ↔ App Insights connection
├── main.adapp.client-spa.tf              # SPA App Registration
├── main.adapp.identity-echo-api.tf       # Identity Echo API App Registration
├── main.containerapp.tf                  # Container Apps environment & UAMI
├── main.containerapp.apps.tf             # Container Apps definitions + ACR build
├── main.swa.tf                           # Static Web App
├── main.loganalytics.tf                  # Log Analytics Workspace
├── main.appinsights.tf                   # Application Insights
├── main.rbac.definitions.tf              # RBAC role definitions (locals)
├── main.rbac.services.tf                 # Service-to-service RBAC assignments
├── main.rbac.users.tf                    # User & group RBAC assignments
│
├── outputs.tf                            # Output values (referenced by sync-infra-env.py)
├── terraform.tfvars.example              # Sample variable configuration
└── terraform.tfvars                      # Actual variable settings (not tracked by git)
```

---

## Azure Resource Layout

### Overview

```text
Resource Group
├── Foundry Resource (Cognitive Account / AIServices)
│   ├── Foundry Project (System-Assigned MI)
│   │   └── Agent Identity Blueprint + Agent Identity (auto-created)
│   ├── Capability Host (Hosted Agent execution environment)
│   ├── Model Deployment (gpt-4.1, etc.)
│   └── Connection (App Insights)
├── Azure Container Registry (Basic)
├── Container Apps Environment
│   ├── Identity Echo API (Container App)
│   └── Backend API (Container App)
├── Static Web App (Free)
├── Log Analytics Workspace
├── Application Insights
├── Entra ID App Registration × 2
│   ├── SPA (demo-client-app)
│   └── Identity Echo API (demo-identity-echo-api)
└── RBAC Role Assignments
```

### Foundry Resource Hierarchy

All Foundry-specific resources are under `Microsoft.CognitiveServices`:

```text
azurerm_cognitive_account (kind: AIServices)
├── azurerm_cognitive_account_project     ← Foundry Project (MI holds the Agent Identity)
├── azapi_resource (capabilityHosts)      ← Hosted Agent execution environment
├── azurerm_cognitive_deployment (×N)     ← LLM model deployments
└── azapi_resource (connections)          ← Connection to App Insights
```

> When a Foundry Project is created, the Agent Identity Blueprint and Agent Identity are automatically provisioned.
> They don't need to be directly managed by Terraform, but their Client IDs are retrieved via `outputs.tf`.

---

## Required Variables

### Mandatory Variables

| Variable                        | Description                     | Example               |
| ------------------------------- | ------------------------------- | --------------------- |
| `tenant_id`                     | Entra ID tenant ID              | `"xxxxxxxx-xxxx-..."` |
| `target_subscription_id`        | Azure subscription ID           | `"xxxxxxxx-xxxx-..."` |
| `location`                      | Azure region                    | `"eastus2"`           |
| `cognitive_project_name`        | Foundry Project name            | `"my-project"`        |
| `cognitive_project_description` | Foundry Project description     | `"Demo project"`      |
| `cognitive_deployments`         | LLM model deployment definition | (see tfvars.example)  |
| `container_apps`                | Container Apps definition       | (see tfvars.example)  |

### Key Optional Variables

| Variable                           | Default              | Description                                     |
| ---------------------------------- | -------------------- | ----------------------------------------------- |
| `naming_suffix`                    | `["foundry", "poc"]` | Resource name prefix                            |
| `env`                              | `"dev"`              | Environment identifier                          |
| `is_production`                    | `false`              | Controls delete protection & Soft-Delete purge  |
| `swa_location`                     | `"eastus2"`          | SWA region (can differ from the main region)    |
| `ai_project_developers_group_name` | `""`                 | Developer group (for RBAC assignment)           |
| `ai_project_users_group_name`      | `""`                 | User group (for RBAC assignment)                |
| `enable_cognitive_local_auth`      | `false`              | Enable API key authentication (not recommended) |

---

## RBAC Role Assignments

### Service-to-Service

| Assignee                   | Target            | Role                                          | Purpose                             |
| -------------------------- | ----------------- | --------------------------------------------- | ----------------------------------- |
| Foundry Project MI         | Cognitive Account | Cognitive Services User                       | Hosted Agent calls the LLM          |
| Foundry Project MI         | ACR               | AcrPull, Container Registry Repository Reader | Hosted Agent pulls images           |
| Container Apps shared UAMI | ACR               | AcrPull                                       | Container Apps pull images          |
| Backend API dedicated UAMI | Cognitive Account | Cognitive Services User                       | Backend API calls the Foundry Agent |

### Users & Groups

| Assignee        | Role               | Condition                          |
| --------------- | ------------------ | ---------------------------------- |
| Deployer        | Azure AI Owner     | Always (Account + Project)         |
| Developer group | Azure AI Developer | Only when group name is configured |
| User group      | Azure AI User      | Only when group name is configured |

---

## Naming Conventions

Resource names are auto-generated in `_locals.naming.tf`.
SHA256 hashes and random strings ensure global uniqueness:

| Pattern      | Format                                              | Example Use                  |
| ------------ | --------------------------------------------------- | ---------------------------- |
| longName     | `{prefix}-{project}-{env}-{region}-{hash6}`         | Resource Group, App Insights |
| simpleName   | `{prefix}-{project}-{env}-{region}`                 | Foundry Project              |
| alphanumName | `{prefix}{proj5}{env3}{hash14}` (alphanumeric only) | ACR                          |

---

## Terraform Output Values

Approximately 30 values are exported in `outputs.tf`. Key outputs:

| Output                                | Description                      | `.env` Variable                            |
| ------------------------------------- | -------------------------------- | ------------------------------------------ |
| `tenant_id`                           | Tenant ID                        | `ENTRA_TENANT_ID`                          |
| `client_app_client_id`                | SPA Client ID                    | `ENTRA_SPA_APP_CLIENT_ID`                  |
| `resource_api_client_id`              | Identity Echo API Client ID      | `ENTRA_RESOURCE_API_CLIENT_ID`             |
| `resource_api_scope`                  | Delegated scope                  | `ENTRA_RESOURCE_API_SCOPE`                 |
| `foundry_project_endpoint`            | Foundry endpoint                 | `FOUNDRY_PROJECT_ENDPOINT`                 |
| `foundry_agent_identity_id`           | Agent Identity Client ID         | `ENTRA_AGENT_IDENTITY_CLIENT_ID`           |
| `foundry_agent_identity_blueprint_id` | Blueprint Client ID              | `ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID` |
| `acr_login_server`                    | ACR login server                 | `FOUNDRY_AGENT_ACR_LOGIN_SERVER`           |
| `resource_api_url`                    | Identity Echo API URL            | `RESOURCE_API_URL`                         |
| `backend_api_url`                     | Backend API URL                  | `BACKEND_API_URL`                          |
| `swa_deployment_token`                | SWA deployment token (sensitive) | (referenced directly by deploy-swa.py)     |

> `sync-infra-env.py` runs `terraform output -json` and automatically syncs these values to `src/.env`.

---

## Behavior on Initial Apply

`terraform apply` creates resources in the following order:

1. Resource Group
2. Entra ID App Registration × 2
3. Foundry Resource → Project → Capability Host → Model Deployment
4. ACR → Build Container images via `az acr build` (null_resource)
5. Container Apps Environment → Wait for RBAC propagation (60 seconds) → Container Apps
6. Static Web App
7. RBAC Role Assignments (service-to-service + users)
