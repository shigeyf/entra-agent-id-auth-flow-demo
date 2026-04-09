# main.cognitive.tf

resource "azurerm_cognitive_account" "this" {
  name                = local.cognitive_account_name
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  tags                = local.tags

  custom_subdomain_name         = local.cognitive_account_name
  kind                          = "AIServices"
  local_auth_enabled            = var.enable_cognitive_local_auth
  project_management_enabled    = true
  public_network_access_enabled = true
  sku_name                      = var.cognitive_account_sku

  identity {
    type = "SystemAssigned"
  }

  network_acls {
    default_action = "Allow"
    bypass         = "AzureServices"
  }
}
