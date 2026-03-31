# main.adapp.client-spa.tf

resource "azuread_application" "client_spa" {
  display_name = var.client_app_display_name

  sign_in_audience = "AzureADMyOrg"

  single_page_application {
    redirect_uris = var.client_app_redirect_uris
  }

  # API Permission: Identity Echo API — CallerIdentity.Read (Delegated)
  required_resource_access {
    resource_app_id = azuread_application.resource_api.client_id

    resource_access {
      id   = random_uuid.delegated_scope_id.result
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
