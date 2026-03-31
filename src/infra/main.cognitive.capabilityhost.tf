# main.cognitive.capabilityhost.tf

/*
  Account-level Capability Host for Foundry Agent Service (Hosted Agents).

  Hosted Agents require an account-level capability host with public hosting
  environment enabled. This resource type is not yet available in the azurerm
  provider, so we use the azapi provider with the ARM API directly.

  Why azapi_resource (not azapi_resource_action):
    azapi_resource waits for the Managed Environment provisioning to complete
    before returning. azapi_resource_action only fires the PUT and returns
    immediately, which causes agent deployments to fail with a timeout error
    because the environment is not yet ready.

  Destroy handling:
    The capabilityHosts API does not support DELETE. Before running
    `terraform destroy`, remove this resource from state:
      terraform state rm azapi_resource.capability_host

  Use API version: 2025-10-01-preview
    NOTE: The official docs still reference 2025-10-01-preview as of 2025-03-31,
      but 2025-12-01 is the GA version listed in the ARM template reference.
    NOTE: New version is 2025-12-01 (GA).
      The 2025-10-01-preview version is required to avoid a "The request is not valid" error.

  Reference:
    https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents#create-an-account-level-capability-host
    https://learn.microsoft.com/en-us/azure/templates/microsoft.cognitiveservices/accounts/capabilityhosts
*/

resource "azapi_resource" "capability_host" {
  type      = "Microsoft.CognitiveServices/accounts/capabilityHosts@2025-10-01-preview"
  name      = "accountcaphost"
  parent_id = azurerm_cognitive_account.this.id

  body = {
    properties = {
      capabilityHostKind             = "Agents"
      enablePublicHostingEnvironment = true
    }
  }
}
