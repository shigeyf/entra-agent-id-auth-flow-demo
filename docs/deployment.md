# Deployment Guide — Redeployment & Operations Reference

[English](./deployment.md) | [日本語](./deployment.ja.md)

This guide covers redeployment procedures after code changes and deployment details for each component.

> **Initial setup**: For the step-by-step guide from environment setup through deployment,
> see [Getting Started](getting-started.md). This document assumes that
> sections 1–7 of Getting Started have already been completed.

## Prerequisites

- Sections 1–7 of [Getting Started](getting-started.md) are complete
- Logged in to Azure CLI (`az login`)
- Docker available (for Hosted Agent builds)

---

## Deployment Pipeline Overview

```text
terraform apply  ──→  sync-infra-env.py  ──┬──→  deploy-container-apps.py
(on infra changes)    (re-sync .env)       │     (Backend API / Identity Echo API)
                                           │
                                           ├──→  deploy-swa.py
                                           │     (Frontend SPA)
                                           │
                                           └──→  deploy-agent.py
                                                  (Hosted Agent)
```

> Container Apps, SWA, and Hosted Agent deployments are independent of each other and can run in parallel.

---

## Quick Reference for Updates

After code changes, redeploy only the affected component:

| What Changed                | Redeploy Command                                                                      |
| --------------------------- | ------------------------------------------------------------------------------------- |
| Identity Echo API code      | `python src/scripts/deploy-container-apps.py identity-echo-api`                       |
| Backend API code            | `python src/scripts/deploy-container-apps.py backend-api`                             |
| Frontend SPA code           | `python src/frontend/scripts/deploy-swa.py`                                           |
| Hosted Agent code           | `cd src/agent && python scripts/deploy-agent.py build push deploy --start --wait`     |
| Terraform definitions       | `cd src/infra && terraform apply && cd ../.. && python src/scripts/sync-infra-env.py` |
| Environment variable change | `python src/scripts/sync-infra-env.py` → redeploy affected components                 |

---

## Container Apps (Backend API / Identity Echo API)

### Deploy All

```bash
python src/scripts/deploy-container-apps.py
```

### Deploy Individually

```bash
# Identity Echo API only
python src/scripts/deploy-container-apps.py identity-echo-api

# Backend API only
python src/scripts/deploy-container-apps.py backend-api
```

### What It Does

1. Reads ACR name, resource group, and other values from `src/.env`
2. Builds the container image and pushes to ACR via `az acr build`
3. Updates the Container App to the latest image via `az containerapp update`

> **Note**: The initial `terraform apply` automatically deploys Container Apps,
> so this script is used for **redeployment** after code changes.

### Verifying the Deployment

```bash
# Identity Echo API
curl https://<identity-echo-api-fqdn>/health

# Backend API
curl https://<backend-api-fqdn>/health
```

FQDNs can be obtained with `cd src/infra && terraform output container_app_urls`.

---

## Frontend SPA (Static Web Apps)

### Deploy

```bash
python src/frontend/scripts/deploy-swa.py
```

### Redeploy Without Rebuilding

```bash
python src/frontend/scripts/deploy-swa.py --skip-build
```

### What It Does

1. Reads cloud environment variables (API URLs, Entra ID settings) from `src/.env`
2. Generates a temporary `src/.env.production` (embeds cloud URLs at build time)
3. Runs `npm run build` for the Vite build (TypeScript compilation + bundling)
4. Retrieves the SWA deployment token from `terraform output`
5. Deploys `dist/` to Static Web Apps via `swa deploy`

### Vite Environment Variables

Vite embeds environment variables at build time. `deploy-swa.py` passes the following values
from `src/.env` to Vite via `.env.production`:

| Environment Variable           | Purpose                     |
| ------------------------------ | --------------------------- |
| `ENTRA_TENANT_ID`              | MSAL tenant configuration   |
| `ENTRA_SPA_APP_CLIENT_ID`      | MSAL client ID              |
| `ENTRA_RESOURCE_API_CLIENT_ID` | Resource API audience       |
| `ENTRA_RESOURCE_API_SCOPE`     | Scope for token requests    |
| `RESOURCE_API_URL`             | Identity Echo API cloud URL |
| `BACKEND_API_URL`              | Backend API cloud URL       |

> **Local vs. Cloud**: During local development, `src/.env` is read directly.
> For cloud deployment, cloud URLs are written to `.env.production` before the Vite build.

### Verifying the Deployment

```bash
cd src/infra && terraform output frontend_spa_app_url
```

Open the output URL in a browser and verify that the SPA loads.

---

## Hosted Agent

### Deploy

```bash
cd src/agent
python scripts/deploy-agent.py build push deploy --start --wait
```

### What It Does

| Step       | Action                                | Details                                                        |
| ---------- | ------------------------------------- | -------------------------------------------------------------- |
| **build**  | `docker build --platform linux/amd64` | Builds the Agent runtime container image                       |
| **push**   | `az acr login` → `docker push`        | Pushes the image to ACR                                        |
| **deploy** | `create_version()`                    | Creates a Foundry Agent Version based on `agent.yaml`          |
| **start**  | `az cognitiveservices agent start`    | Starts the Hosted Agent, making it available via Responses API |

### Running Individual Steps

```bash
cd src/agent

# Build and push only (no deploy/start)
python scripts/deploy-agent.py build push

# Deploy and start only (when the image is already in ACR)
python scripts/deploy-agent.py deploy --start --wait
```

> **Agent Version Idempotency**: The `create_version` API is idempotent. If the definition
> (image URI, environment variables, etc.) is identical to the previous version, no new version
> is created and the existing version is returned. The script detects this and performs
> `delete-deployment` → `start` to swap the container image.

### Verification

```bash
cd src/agent
python scripts/invoke-agent.py --tool call_resource_api_autonomous_app
```

---

## Troubleshooting

### CORS Errors

If CORS errors occur on API calls from the SPA:

1. Verify that `FRONTEND_SPA_APP_URL` in `src/.env` is set correctly
2. Ensure the environment variables are reflected after redeploying Container Apps

```bash
# Redeploy Container Apps to apply environment variables
python src/scripts/deploy-container-apps.py
```

### ACR Build Errors

**`unauthorized: authentication required`**:

```bash
az acr login --name <acr-name>
```

**Build timeout**:
The default ACR build timeout is 600 seconds. You may need to increase it depending on network conditions.

### Hosted Agent Fails to Start

1. Check the Agent status:

   ```bash
   az cognitiveservices agent show \
     --account-name <cognitive-account-name> \
     --project-name <project-name> \
     --resource-group <resource-group>
   ```

2. Verify that the Capability Host is properly provisioned

3. Confirm that the ACR image was built for the `linux/amd64` platform

### `swa_deployment_token` Error During SWA Deployment

```text
ERROR: could not read swa_deployment_token from terraform output
```

Verify that the Terraform state is in `src/infra` and that the SWA resource has been created:

```bash
cd src/infra && terraform output swa_deployment_token
```

---

## Related Documentation

- [Getting Started](getting-started.md) — Initial setup & local launch
- [Architecture](architecture.md) — Component layout details
- [Hosted Agent Details](../src/agent/README.md) — Agent architecture & deployment lifecycle
