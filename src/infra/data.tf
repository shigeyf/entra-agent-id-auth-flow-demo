# data.tf

data "azurerm_client_config" "current" {}

data "azuread_group" "ai_developer_group" {
  count            = var.ai_project_developers_group_name != "" ? 1 : 0
  display_name     = var.ai_project_developers_group_name
  security_enabled = true
}

data "azuread_group" "ai_user_group" {
  count            = var.ai_project_users_group_name != "" ? 1 : 0
  display_name     = var.ai_project_users_group_name
  security_enabled = true
}
