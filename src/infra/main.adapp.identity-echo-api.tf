// main.adapp.identity-echo-api.tf

# Stable UUIDs for scope / role (generated once, deterministic)
resource "random_uuid" "delegated_scope_id" {}
resource "random_uuid" "app_role_id" {}

resource "azuread_application" "resource_api" {
  display_name = var.resource_api_display_name

  sign_in_audience = "AzureADMyOrg"

  # App ID URI — set after creation via azuread_application_identifier_uri
  # (identifier_uris requires the Application ID which is computed)

  api {
    requested_access_token_version = 2

    # Delegated permission: CallerIdentity.Read
    oauth2_permission_scope {
      id                         = random_uuid.delegated_scope_id.result
      value                      = var.resource_api_delegated_scope_name
      type                       = "User"
      admin_consent_display_name = var.resource_api_delegated_scope_name
      admin_consent_description  = var.resource_api_delegated_scope_description
      user_consent_display_name  = var.resource_api_delegated_scope_name
      user_consent_description   = var.resource_api_delegated_scope_description
      enabled                    = true
    }
  }

  # Application permission (App Role): CallerIdentity.Read.All
  app_role {
    id                   = random_uuid.app_role_id.result
    value                = var.resource_api_app_role_name
    display_name         = var.resource_api_app_role_name
    description          = var.resource_api_app_role_description
    allowed_member_types = ["Application"]
    enabled              = true
  }

  lifecycle {
    ignore_changes = [identifier_uris]
  }
}

# App ID URI: api://<application_id>
resource "azuread_application_identifier_uri" "resource_api" {
  application_id = azuread_application.resource_api.id
  identifier_uri = "api://${azuread_application.resource_api.client_id}"
}

# Service Principal (Enterprise Application)
resource "azuread_service_principal" "resource_api" {
  client_id = azuread_application.resource_api.client_id
}
