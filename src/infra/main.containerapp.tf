# main.containerapp.tf

/*
  Azure Container Apps Environment for hosting the Identity Echo API
  (Phase 2 Step A-4) and Backend API (Phase 2 Step C).

  Log Analytics Workspace is defined in main.loganalytics.tf (shared with App Insights).
*/

resource "azurerm_container_app_environment" "this" {
  name                = local.container_apps_env_name
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = local.tags

  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
}

/*
  User-Assigned Managed Identity shared by all Container Apps.

  Created before the Container Apps themselves so that AcrPull RBAC can be
  granted before the first image pull, avoiding the chicken-and-egg problem
  that occurs with System-Assigned MI (which only exists after the app is created).
*/
resource "azurerm_user_assigned_identity" "container_apps" {
  name                = local.container_apps_identity_name
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = local.tags
}

/*
  User-Assigned Managed Identity dedicated to the Backend API.

  Granted Cognitive Services User on the Foundry Account so that the Backend API
  can invoke the Hosted Agent via the OpenAI Responses API.  The AZURE_CLIENT_ID
  environment variable in the Container App points to this UAMI's client_id,
  ensuring DefaultAzureCredential() selects it over the shared ACR-pull UAMI.
*/
resource "azurerm_user_assigned_identity" "backend_api" {
  name                = local.backend_api_identity_name
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = local.tags
}
