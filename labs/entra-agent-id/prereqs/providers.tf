# providers.tf

provider "azuread" {
  tenant_id = var.tenant_id == "" ? null : var.tenant_id
}
