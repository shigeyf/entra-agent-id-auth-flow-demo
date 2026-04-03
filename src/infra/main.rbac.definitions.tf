# main.rbac.definitions.tf

/*
  Centralized RBAC role definitions for Azure AI Foundry ecosystem.

  Description:
    Centralizes all role names used in RBAC assignments.
    Each Identity × Scope pair has its own locals entry for easy
    change management, auditing, and review.

    Terraform can reference Azure built-in roles by name,
    so GUID management (as in Bicep's roleDefinitions.bicep) is unnecessary.

    Referenced by the following RBAC files:
      - main.rbac.services.tf: Service-to-service RBAC
      - main.rbac.cmk.tf:      CMK encryption RBAC
      - main.rbac.users.tf:    User/group RBAC
*/

locals {
  # ---------------------------------------------------------------------------
  # Service-to-service RBAC role definitions (main.rbac.services.tf)
  # ---------------------------------------------------------------------------

  # Foundry Project → Foundry Account (Parent-child RBAC)
  # The Hosted Agent container runs as the Foundry Project MI. This grants it permission
  # to call GPT-4.1 and text-embedding-3-small via DefaultAzureCredential inside @ai_function tools.
  roles_foundry_project_to_foundry_account = toset([
    "Cognitive Services User",
  ])

  # Foundry Project → ACR (Container image pull)
  # The Hosted Agent runtime pulls container images using the Foundry Project MI.
  # Docs recommend "Container Registry Repository Reader" (data-plane) but the
  # Container Apps hosting environment also requires "AcrPull" (control-plane)
  # for the actual image pull operation.
  # Reference: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents#configure-azure-container-registry-permissions
  roles_foundry_project_to_acr = toset([
    "AcrPull",
    "Container Registry Repository Reader",
  ])

  # Container Apps UAMI → ACR (Container image pull)
  # The shared User-Assigned Managed Identity pulls images from ACR.
  # RBAC is assigned before Container App creation to avoid the chicken-and-egg
  # problem that occurs with System-Assigned MI.
  roles_container_app_to_acr = toset([
    "AcrPull",
  ])
}

locals {
  # ---------------------------------------------------------------------------
  # Deployer RBAC role definitions (main.rbac.users.tf)
  # ---------------------------------------------------------------------------

  # Grants the deployment user (identified by az login / service principal)
  # the same set of roles as the Bicep deployer, enabling Foundry portal
  # access and resource management without subscription-level access.

  # Deployer → Foundry Account
  roles_deployer_to_foundry_account = toset([
    "Azure AI Owner",
  ])

  # Deployer → Foundry Project
  roles_deployer_to_foundry_project = toset([
    "Azure AI Owner",
  ])

  # ---------------------------------------------------------------------------
  # AI Developer Group RBAC role definitions (main.rbac.users.tf)
  # ---------------------------------------------------------------------------

  # Developer Group → Foundry Account
  # Azure AI Developer: permissions to create and manage models, deployments, and agents
  roles_developer_group_to_foundry_account = toset([
    "Azure AI Developer",
  ])

  # Developer Group → Foundry Project
  roles_developer_group_to_foundry_project = toset([
    "Azure AI Developer",
  ])

  # ---------------------------------------------------------------------------
  # AI User Group RBAC role definitions (main.rbac.users.tf)
  # ---------------------------------------------------------------------------

  # Grants users read-only access to AI resources and the ability to use
  # deployed models and agents without modification privileges.
  # Pass empty string for ai_project_users_group_name to skip.

  # User Group → Foundry Account (read-only)
  roles_user_group_to_foundry_account = toset([
    "Azure AI User",
  ])

  # User Group → Foundry Project (read-only)
  roles_user_group_to_foundry_project = toset([
    "Azure AI User",
  ])
}
