# main.cognitive.project.tf

resource "azurerm_cognitive_account_project" "this" {
  name                 = local.cognitive_project_name
  cognitive_account_id = azurerm_cognitive_account.this.id
  location             = var.location
  tags                 = local.tags

  description  = var.cognitive_project_description
  display_name = var.cognitive_project_name

  identity {
    type = "SystemAssigned"
  }
}
