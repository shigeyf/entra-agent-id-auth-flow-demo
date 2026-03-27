// outputs.tf

# -----------------------------------------------------------------------------
# Identity Echo API (Resource API)
# -----------------------------------------------------------------------------

output "resource_api_client_id" {
  description = "Identity Echo API Application (client) ID — set as RESOURCE_API_CLIENT_ID in .env"
  value       = azuread_application.resource_api.client_id
}

output "resource_api_object_id" {
  description = "Identity Echo API Application Object ID"
  value       = azuread_application.resource_api.object_id
}

output "resource_api_scope" {
  description = "Fully qualified delegated scope name — set as RESOURCE_API_SCOPE in .env"
  value       = "api://${azuread_application.resource_api.client_id}/${var.resource_api_delegated_scope_name}"
}

output "resource_api_default_scope" {
  description = "Application scope (.default) — set as RESOURCE_API_DEFAULT_SCOPE in .env"
  value       = "api://${azuread_application.resource_api.client_id}/.default"
}

# -----------------------------------------------------------------------------
# Client SPA
# -----------------------------------------------------------------------------

output "client_app_client_id" {
  description = "SPA Application (client) ID — set as VITE_MSAL_CLIENT_ID in .env"
  value       = azuread_application.client_spa.client_id
}

output "client_app_object_id" {
  description = "SPA Application Object ID"
  value       = azuread_application.client_spa.object_id
}
