# main.appinsights.tf

/*
  Application Insights for observability across the Foundry project
  and Container Apps.

  The Foundry connection (linking this App Insights to the Foundry account)
  is defined in main.cognitive.connection.appinsights.tf.
*/

resource "azurerm_application_insights" "this" {
  name                = local.appinsights_name
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = local.tags

  application_type = "web"
  workspace_id     = azurerm_log_analytics_workspace.this.id
}
