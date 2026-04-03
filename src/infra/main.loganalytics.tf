# main.loganalytics.tf

/*
  Shared Log Analytics Workspace.

  Used by:
    - Container Apps Environment (container logs)
    - Application Insights (telemetry backend)
*/

resource "azurerm_log_analytics_workspace" "this" {
  name                = local.log_analytics_workspace_name
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = local.tags

  sku               = "PerGB2018"
  retention_in_days = 30
}
