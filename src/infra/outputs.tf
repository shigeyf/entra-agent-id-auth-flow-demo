# outputs.tf

# -----------------------------------------------------------------------------
# Tenant ID
# -----------------------------------------------------------------------------

output "tenant_id" {
  description = "Azure Tenant ID - set as ENTRA_TENANT_ID in .env"
  value       = data.azurerm_client_config.current.tenant_id
}

# -----------------------------------------------------------------------------
# Identity Echo API (Resource API)
# -----------------------------------------------------------------------------

output "resource_api_client_id" {
  description = "Identity Echo API Application (client) ID — set as ENTRA_RESOURCE_API_CLIENT_ID in .env"
  value       = azuread_application.resource_api.client_id
}

output "resource_api_object_id" {
  description = "Identity Echo API Application Object ID"
  value       = azuread_application.resource_api.object_id
}

output "resource_api_scope" {
  description = "Fully qualified delegated scope name — set as ENTRA_RESOURCE_API_SCOPE in .env"
  value       = "api://${azuread_application.resource_api.client_id}/${var.resource_api_delegated_scope_name}"
}

output "resource_api_default_scope" {
  description = "Application scope (.default) — set as ENTRA_RESOURCE_API_DEFAULT_SCOPE in .env"
  value       = "api://${azuread_application.resource_api.client_id}/.default"
}

# -----------------------------------------------------------------------------
# Client SPA
# -----------------------------------------------------------------------------

output "client_app_client_id" {
  description = "SPA Application (client) ID — set as ENTRA_SPA_APP_CLIENT_ID in .env"
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
  description = "Azure Container Registry name (used for docker push)"
  value       = azurerm_container_registry.this.name
}

output "acr_login_server" {
  description = "ACR login server URL (used as image prefix) - set as FOUNDRY_AGENT_ACR_LOGIN_SERVER in .env"
  value       = azurerm_container_registry.this.login_server
}

# -----------------------------------------------------------------------------
# Microsoft Foundry
# -----------------------------------------------------------------------------

# Filter inference (non-embedding) deployments from the deployment list
locals {
  inference_deployments = [
    for d in var.cognitive_deployments : d
    if !startswith(d.model, "text-embedding-")
  ]
}

output "cognitive_account_name" {
  description = "Foundry (Cognitive Services) account name"
  value       = azurerm_cognitive_account.this.name
}

output "cognitive_account_endpoint" {
  description = "Foundry account endpoint"
  value       = azurerm_cognitive_account.this.endpoint
}

output "cognitive_project_name" {
  description = "Foundry project name"
  value       = azurerm_cognitive_account_project.this.name
}

# Obtain Foundry Project Resource with new API version
# to get additional properties not included in the older API version,
# such as properties.agentIdentity.
data "azapi_resource" "foundry_project" {
  name      = azurerm_cognitive_account_project.this.name
  parent_id = azurerm_cognitive_account.this.id
  type      = "Microsoft.CognitiveServices/accounts/projects@2025-12-01"

  response_export_values = ["properties"]
}

output "foundry_agent_identity_id" {
  description = "Entra Agent Identity ID — set as ENTRA_AGENT_IDENTITY_CLIENT_ID in .env"
  value       = data.azapi_resource.foundry_project.output.properties.agentIdentity.agentIdentityId
}

output "foundry_agent_identity_blueprint_id" {
  description = "Entra Agent Identity Blueprint ID - set as ENTRA_AGENT_BLUEPRINT_IDENTITY_CLIENT_ID in .env"
  value       = data.azapi_resource.foundry_project.output.properties.agentIdentity.agentIdentityBlueprintId
}

output "foundry_project_endpoint" {
  description = "Foundry project endpoint — set as FOUNDRY_PROJECT_ENDPOINT in .env"
  value       = "${azurerm_cognitive_account.this.endpoint}api/projects/${azurerm_cognitive_account_project.this.name}"
}

output "foundry_model_deployment_name" {
  description = "First inference (non-embedding) model deployment name — set as FOUNDRY_MODEL_DEPLOYMENT_NAME in .env"
  value       = length(local.inference_deployments) > 0 ? local.inference_deployments[0].name : ""
}

output "foundry_project_principal_id" {
  description = "Foundry project system-assigned managed identity principal ID"
  value       = azurerm_cognitive_account_project.this.identity[0].principal_id
}
