# providers.tf

provider "azuread" {
  tenant_id = var.tenant_id
}

provider "azurerm" {
  storage_use_azuread = true
  subscription_id     = var.target_subscription_id == "" ? null : var.target_subscription_id
  features {
    resource_group {
      # For demo/dev environments, allow deletion even with resources inside
      # For production, prevent accidental deletion of resource groups with resources
      prevent_deletion_if_contains_resources = var.is_production
    }
    cognitive_account {
      # For demo/dev environments, purge soft-deleted items on destroy for clean teardown
      # For production, keep soft-delete protection to prevent accidental data loss
      purge_soft_delete_on_destroy = !var.is_production
    }
  }
}

provider "azapi" {
  subscription_id = var.target_subscription_id == "" ? null : var.target_subscription_id
}
