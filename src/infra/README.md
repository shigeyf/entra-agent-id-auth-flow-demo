# Infrastructure (Terraform)

[English](./README.md) | [日本語](./README.ja.md)

This directory contains Terraform templates for provisioning the Azure resources used by the demo app.

## Quick Start

```bash
cd src/infra

# Create variables file (first time only)
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars to set tenant_id, subscription_id, etc.

terraform init
terraform plan
terraform apply
```

## File Structure Overview

| File                                           | Contents                                    |
| ---------------------------------------------- | ------------------------------------------- |
| `terraform.tf`                                 | Terraform & provider version constraints    |
| `providers.tf`                                 | Provider configuration                      |
| `_variables*.tf`                               | Input variables (core, tags, Foundry, Apps) |
| `_locals*.tf`                                  | Naming conventions & computed values        |
| `data.tf`                                      | Data sources                                |
| `main.rg.tf`                                   | Resource Group                              |
| `main.cognitive*.tf`                           | Foundry Resource, Project, Capability Host  |
| `main.acr.tf`                                  | Azure Container Registry                    |
| `main.containerapp*.tf`                        | Container Apps environment & apps           |
| `main.adapp*.tf`                               | Entra ID App Registration                   |
| `main.swa.tf`                                  | Static Web App                              |
| `main.rbac*.tf`                                | RBAC role assignments                       |
| `main.loganalytics.tf` / `main.appinsights.tf` | Monitoring resources                        |
| `outputs.tf`                                   | Outputs (referenced by `sync-infra-env.py`) |

## Detailed Documentation

For resource structure, variable reference, RBAC list, naming conventions, and known caveats:

- [Infrastructure Guide](../../docs/infrastructure.md)

For setup instructions:

- [Getting Started](../../docs/getting-started.md) — Section 2: Terraform
