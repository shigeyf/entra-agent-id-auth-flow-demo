# main.acr.tf

/*
  Azure Container Registry for Hosted Agent container images.

  The Foundry Hosted Agent service requires a container image stored in ACR.
  The Project system-assigned managed identity must have pull access to this registry.
*/

resource "azurerm_container_registry" "this" {
  name                = local.acr_name
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = local.tags

  sku                           = "Basic"
  admin_enabled                 = false
  public_network_access_enabled = true
}
