# outputs.tf

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

# -----------------------------------------------------------------------------
# Azure Container Registry
# -----------------------------------------------------------------------------

output "acr_name" {
  description = "Azure Container Registry name — used for docker push"
  value       = azurerm_container_registry.this.name
}

output "acr_login_server" {
  description = "ACR login server URL — used as image prefix"
  value       = azurerm_container_registry.this.login_server
}

# -----------------------------------------------------------------------------
# Microsoft Foundry
# -----------------------------------------------------------------------------

output "cognitive_account_name" {
  description = "Foundry (Cognitive Services) account name — used in az cognitiveservices agent commands"
  value       = azurerm_cognitive_account.this.name
}

output "cognitive_account_endpoint" {
  description = "Foundry account endpoint"
  value       = azurerm_cognitive_account.this.endpoint
}

output "cognitive_project_name" {
  description = "Foundry project name — used in az cognitiveservices agent commands"
  value       = azurerm_cognitive_account_project.this.name
}

output "foundry_project_endpoint" {
  description = "Foundry project endpoint — set as PROJECT_ENDPOINT in agent .env"
  value       = "${azurerm_cognitive_account.this.endpoint}api/projects/${azurerm_cognitive_account_project.this.name}"
}

output "foundry_project_principal_id" {
  description = "Foundry project system-assigned managed identity principal ID"
  value       = azurerm_cognitive_account_project.this.identity[0].principal_id
}
