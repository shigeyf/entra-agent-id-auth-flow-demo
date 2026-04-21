# main.tf
#
# Agent ID Manager — Public client App Registration with delegated
# Microsoft Graph permissions for Entra Agent ID management.
#
# This replaces the setup-app-registration.py script with a declarative
# Terraform configuration.

# ---------------------------------------------------------------------------
# Data: Microsoft Graph service principal (for scope ID resolution)
# ---------------------------------------------------------------------------

data "azuread_service_principal" "msgraph" {
  client_id = "00000003-0000-0000-c000-000000000000" # Microsoft Graph
}

data "azuread_client_config" "current" {}

data "azurerm_client_config" "current" {}

locals {
  # Build a map of scope name → scope ID from the Microsoft Graph SP
  msgraph_scope_map = {
    for s in data.azuread_service_principal.msgraph.oauth2_permission_scopes :
    s.value => s.id
  }

  # Delegated scopes required for Agent ID management
  delegated_scopes = [
    "AgentIdentity.DeleteRestore.All",
    "AgentIdentity.EnableDisable.All",
    "AgentIdentity.Read.All",
    "AgentIdentity.ReadWrite.All",
    "AgentIdentityBlueprint.AddRemoveCreds.All",
    "AgentIdentityBlueprint.Create",
    "AgentIdentityBlueprint.DeleteRestore.All",
    "AgentIdentityBlueprint.Read.All",
    "AgentIdentityBlueprint.ReadWrite.All",
    "AgentIdentityBlueprint.UpdateAuthProperties.All",
    "AgentIdentityBlueprint.UpdateBranding.All",
    "AgentIdentityBlueprintPrincipal.Create",
    "AgentIdentityBlueprintPrincipal.DeleteRestore.All",
    "AgentIdentityBlueprintPrincipal.EnableDisable.All",
    "AgentIdentityBlueprintPrincipal.Read.All",
    "AgentIdentityBlueprintPrincipal.ReadWrite.All",
    "AgentIdUser.ReadWrite.All",
    "AgentIdUser.ReadWrite.IdentityParentedBy",
    "AgentInstance.Read.All",
    "AgentInstance.ReadWrite.All",
    "Application.Read.All",
    "Application.ReadWrite.OwnedBy",
    "AppRoleAssignment.ReadWrite.All",
    "DelegatedPermissionGrant.ReadWrite.All",
    "User.Read",
    "User.Read.All",
  ]

  # Filter to only scopes that exist in the tenant
  resolved_scopes = {
    for name in local.delegated_scopes :
    name => local.msgraph_scope_map[name]
    if contains(keys(local.msgraph_scope_map), name)
  }
}

# ---------------------------------------------------------------------------
# App Registration
# ---------------------------------------------------------------------------

resource "azuread_application" "agent_id_manager" {
  display_name     = var.app_display_name
  sign_in_audience = "AzureADMyOrg"

  owners = [data.azurerm_client_config.current.object_id]

  fallback_public_client_enabled = true

  public_client {
    redirect_uris = ["http://localhost"]
  }

  required_resource_access {
    resource_app_id = data.azuread_service_principal.msgraph.client_id

    dynamic "resource_access" {
      for_each = local.resolved_scopes
      content {
        id   = resource_access.value
        type = "Scope" # Delegated
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Service Principal (Enterprise Application)
# ---------------------------------------------------------------------------

resource "azuread_service_principal" "agent_id_manager" {
  client_id                    = azuread_application.agent_id_manager.client_id
  app_role_assignment_required = var.app_role_assignment_required

  tags = ["HideApp", "WindowsAzureActiveDirectoryIntegratedApp"]
}

# ---------------------------------------------------------------------------
# Admin Consent — grant all delegated scopes tenant-wide
# ---------------------------------------------------------------------------

resource "azuread_service_principal_delegated_permission_grant" "agent_id_manager_to_msgraph" {
  service_principal_object_id          = azuread_service_principal.agent_id_manager.object_id
  resource_service_principal_object_id = data.azuread_service_principal.msgraph.object_id
  claim_values                         = keys(local.resolved_scopes)
}

# ---------------------------------------------------------------------------
# User / Group Assignments (only effective when assignment_required = true)
# ---------------------------------------------------------------------------

# Default Access role ID (well-known zero GUID)
locals {
  default_access_role_id = "00000000-0000-0000-0000-000000000000"
}

# Always assign the current Terraform executor
resource "azuread_app_role_assignment" "current_user" {
  app_role_id         = local.default_access_role_id
  principal_object_id = data.azuread_client_config.current.object_id
  resource_object_id  = azuread_service_principal.agent_id_manager.object_id
}

# Additional user assignments
resource "azuread_app_role_assignment" "users" {
  for_each = toset(var.assigned_user_object_ids)

  app_role_id         = local.default_access_role_id
  principal_object_id = each.value
  resource_object_id  = azuread_service_principal.agent_id_manager.object_id
}

# Group assignments
resource "azuread_app_role_assignment" "groups" {
  for_each = toset(var.assigned_group_object_ids)

  app_role_id         = local.default_access_role_id
  principal_object_id = each.value
  resource_object_id  = azuread_service_principal.agent_id_manager.object_id
}
