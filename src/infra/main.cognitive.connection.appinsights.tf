# main.cognitive.connection.appinsights.tf

/*
  Foundry Connection — Application Insights

  Links the Application Insights instance to the Foundry account so that
  agent traces and telemetry are visible in the Foundry portal.

  Key design decisions:
    - Connected at the **account** level (parent = cognitive account), not project.
    - isSharedToAll = true → shared with all projects under this account.
    - Only one Application Insights can be connected per project at a time.

  This uses the same API as the official Bicep sample:
    microsoft-foundry/foundry-samples connection-application-insights.bicep

  Reference:
    https://learn.microsoft.com/en-us/azure/foundry/foundry-portal/connections-add
    https://learn.microsoft.com/en-us/azure/templates/microsoft.cognitiveservices/accounts/connections
*/

resource "azapi_resource" "appinsights_connection" {
  type      = "Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview"
  name      = "appinsights"
  parent_id = azurerm_cognitive_account.this.id

  body = {
    properties = {
      category      = "AppInsights"
      authType      = "ApiKey"
      isSharedToAll = true
      target        = azurerm_application_insights.this.instrumentation_key

      credentials = {
        key = azurerm_application_insights.this.connection_string
      }

      metadata = {
        ApiType    = "Azure"
        ResourceId = azurerm_application_insights.this.id
      }
    }
  }
}
