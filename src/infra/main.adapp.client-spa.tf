# main.adapp.client-spa.tf

# ---------------------------------------------------------------------------
# Data sources: Blueprint & Cognitive Services service principals
# ---------------------------------------------------------------------------

# Blueprint SP — Foundry-provisioned, looked up by client_id from project output
data "azuread_service_principal" "blueprint" {
  client_id = data.azapi_resource.foundry_project.output.properties.agentIdentity.agentIdentityBlueprintId
}

# Azure ML / Foundry (ai.azure.com) first-party SP
# The services.ai.azure.com endpoint expects aud=https://ai.azure.com
data "azuread_service_principal" "foundry_api" {
  client_id = "18a66f5f-dbdf-4c17-9dd7-1634712a9cbe" # Azure Machine Learning Services (https://ai.azure.com)
}

# ---------------------------------------------------------------------------
# SPA App Registration
# ---------------------------------------------------------------------------

resource "azuread_application" "client_spa" {
  display_name = var.client_app_display_name

  sign_in_audience = "AzureADMyOrg"

  owners = [data.azurerm_client_config.current.object_id]

  single_page_application {
    redirect_uris = concat(
      var.client_app_redirect_uris,
      ["https://${azurerm_static_web_app.frontend.default_host_name}/"],
    )
  }

  # API Permission: Identity Echo API — CallerIdentity.Read (Delegated)
  required_resource_access {
    resource_app_id = azuread_application.resource_api.client_id

    resource_access {
      id   = random_uuid.delegated_scope_id.result
      type = "Scope" # Delegated
    }
  }

  # API Permission: Blueprint — access_agent (Delegated)
  # Required for Interactive OBO flow: SPA acquires Tc (aud=Blueprint)
  required_resource_access {
    resource_app_id = data.azuread_service_principal.blueprint.client_id

    resource_access {
      id   = [for s in data.azuread_service_principal.blueprint.oauth2_permission_scopes : s.id if s.value == "access_agent"][0]
      type = "Scope" # Delegated
    }
  }

  # API Permission: Azure ML / Foundry (ai.azure.com) — user_impersonation (Delegated)
  # Required for Interactive OBO flow: SPA calls Foundry Agent API directly via services.ai.azure.com
  required_resource_access {
    resource_app_id = data.azuread_service_principal.foundry_api.client_id

    resource_access {
      id   = [for s in data.azuread_service_principal.foundry_api.oauth2_permission_scopes : s.id if s.value == "user_impersonation"][0]
      type = "Scope" # Delegated
    }
  }
}

# Service Principal (Enterprise Application)
resource "azuread_service_principal" "client_spa" {
  client_id = azuread_application.client_spa.client_id
}

# Admin Consent — pre-authorize CallerIdentity.Read delegated permission
resource "azuread_service_principal_delegated_permission_grant" "client_spa_to_resource_api" {
  service_principal_object_id          = azuread_service_principal.client_spa.object_id
  resource_service_principal_object_id = azuread_service_principal.resource_api.object_id
  claim_values                         = [var.resource_api_delegated_scope_name]
}

# Admin Consent — pre-authorize Blueprint access_agent delegated permission
resource "azuread_service_principal_delegated_permission_grant" "client_spa_to_blueprint" {
  service_principal_object_id          = azuread_service_principal.client_spa.object_id
  resource_service_principal_object_id = data.azuread_service_principal.blueprint.object_id
  claim_values                         = ["access_agent"]
}

# Admin Consent — pre-authorize Foundry API (ai.azure.com) user_impersonation delegated permission
resource "azuread_service_principal_delegated_permission_grant" "client_spa_to_foundry_api" {
  service_principal_object_id          = azuread_service_principal.client_spa.object_id
  resource_service_principal_object_id = data.azuread_service_principal.foundry_api.object_id
  claim_values                         = ["user_impersonation"]
}
