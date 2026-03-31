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
