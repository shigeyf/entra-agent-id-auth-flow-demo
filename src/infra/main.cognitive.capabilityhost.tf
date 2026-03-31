# main.cognitive.capabilityhost.tf

/*
  Account-level Capability Host for Foundry Agent Service (Hosted Agents).

  Hosted Agents require an account-level capability host with public hosting
  environment enabled. This resource type is not yet available in the azurerm
  provider, so we use the azapi provider with the ARM API directly.

  API version: 2025-12-01 (GA)
    - azapi v2.9.0 schema does not include 2025-12-01 yet, so
      schema_validation_enabled = false is required.

  Reference:
    https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents#create-an-account-level-capability-host
    https://learn.microsoft.com/en-us/azure/templates/microsoft.cognitiveservices/accounts/capabilityhosts
*/

resource "azapi_resource" "capability_host" {
  type      = "Microsoft.CognitiveServices/accounts/capabilityHosts@2025-12-01"
  name      = "accountcaphost"
  parent_id = azurerm_cognitive_account.this.id

  schema_validation_enabled = false

  body = {
    properties = {
      capabilityHostKind             = "Agents"
      enablePublicHostingEnvironment = true
    }
  }
}
