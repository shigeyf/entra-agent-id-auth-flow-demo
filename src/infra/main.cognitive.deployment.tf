# main.cognitive.deployment.tf

resource "azurerm_cognitive_deployment" "models" {
  for_each             = { for deployment in var.cognitive_deployments : deployment.name => deployment }
  name                 = each.value.name
  cognitive_account_id = azurerm_cognitive_account.this.id
  rai_policy_name      = each.value.rai_policy_name

  model {
    format  = each.value.format
    name    = each.value.model
    version = each.value.version
  }

  sku {
    name     = each.value.sku
    capacity = each.value.capacity
  }
}
