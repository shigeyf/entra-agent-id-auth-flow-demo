# main.rbac.services.tf

/*
  Service-to-service RBAC role assignments for Azure AI Foundry ecosystem.

  Description:
    Centralizes all cross-service RBAC assignments to enable security review
    and auditing from a single location. This file handles permissions between:
      - Foundry Project → Foundry Account (Parent-child RBAC)

    This file is part of the 2-file RBAC structure:
      - main.rbac.services.tf: Service-to-service RBAC (this file)
      - main.rbac.users.tf: User/group RBAC

    Service principals covered:
      - Foundry Project MI → Foundry Account, ACR
      - Container App MIs → ACR (for each app in var.container_apps)
*/

# Foundry Project -> Foundry Account (Parent-child RBAC)
#   The Hosted Agent container runs as the Foundry Project MI. This grants it permission
#   to call GPT-4.1 and text-embedding-3-small via DefaultAzureCredential.
#   Role Definitions: local.roles_foundry_project_to_foundry_account @main.rbac.definitions.tf
resource "azurerm_role_assignment" "cognitive_account_for_cognitive_account_project" {
  for_each             = local.roles_foundry_project_to_foundry_account
  principal_id         = azurerm_cognitive_account_project.this.identity[0].principal_id
  role_definition_name = each.key
  scope                = azurerm_cognitive_account.this.id
}

# Foundry Project -> ACR (Container image pull)
#   The Hosted Agent runtime pulls container images using the Foundry Project MI.
#   Role Definitions: local.roles_foundry_project_to_acr @main.rbac.definitions.tf
resource "azurerm_role_assignment" "acr_for_cognitive_account_project" {
  for_each             = local.roles_foundry_project_to_acr
  principal_id         = azurerm_cognitive_account_project.this.identity[0].principal_id
  role_definition_name = each.key
  scope                = azurerm_container_registry.this.id
}

# Container Apps UAMI -> ACR (Container image pull)
#   The shared User-Assigned MI is granted AcrPull before Container App creation,
#   ensuring the first image pull succeeds without timeout.
#   Role Definitions: local.roles_container_app_to_acr @main.rbac.definitions.tf
resource "azurerm_role_assignment" "acr_for_container_apps" {
  for_each             = local.roles_container_app_to_acr
  principal_id         = azurerm_user_assigned_identity.container_apps.principal_id
  role_definition_name = each.key
  scope                = azurerm_container_registry.this.id
}

# Backend API UAMI -> Foundry Account (Agent invocation)
#   The Backend API invokes the Hosted Agent via OpenAI Responses API.
#   Requires Cognitive Services User on the Foundry Account scope.
#   Uses a dedicated UAMI with AZURE_CLIENT_ID set in the Container App env.
#   Role Definitions: local.roles_backend_api_to_foundry_account @main.rbac.definitions.tf
resource "azurerm_role_assignment" "foundry_account_for_backend_api" {
  for_each             = local.roles_backend_api_to_foundry_account
  principal_id         = azurerm_user_assigned_identity.backend_api.principal_id
  role_definition_name = each.key
  scope                = azurerm_cognitive_account.this.id
}
