# _locals.naming.tf

locals {
  rand_len = 4
}

# Generate a random string for the naming identifier
resource "random_string" "random" {
  length  = local.rand_len
  numeric = true
  lower   = true
  upper   = false
  special = false
}

# Load a module for Azure Region names and short names
module "azure_region" {
  source       = "claranet/regions/azurerm"
  version      = "8.0.2"
  azure_region = var.location
}

/*
  longName     — DNS-globally unique, hyphens allowed, hash suffix appended
                 Pattern: <prefix>-<project>-<env>-<region>-<hash6>    (≤60 chars)
  simpleName   — Scope-unique only (resource group or parent resource), no hash needed
                 Pattern: <prefix>-<project>-<env>-<region>            (≤60 chars)
  shortName    — DNS-globally unique, hyphens allowed, strict length limit (Key Vault etc.)
                 Pattern: <prefix>-<proj4>-<env3>-<hash10>             (≤24 chars)
  alphanumName — DNS-globally unique, no hyphens, strict length limit (ACR, Storage etc.)
                 Pattern: <prefix><proj5><env3><hash14>                (≤24 chars)
*/
locals {
  rand_id             = random_string.random.result
  location_short_name = module.azure_region.location_short

  resource_suffix      = concat(var.naming_suffix, [var.env], [local.location_short_name])
  resource_suffix_hash = sha256(join("", concat(local.resource_suffix, [local.rand_id])))

  hash6 = substr(local.resource_suffix_hash, 0, 6)
  # UNUSED: hash10 = substr(local.resource_suffix_hash, 0, 10)
  hash14 = substr(local.resource_suffix_hash, 0, 14)

  resource_long_name   = "${join("-", local.resource_suffix)}-${local.hash6}"
  resource_simple_name = join("-", local.resource_suffix)
  # UNUSED: resource_short_name    = "${substr(join("", local.resource_suffix), 0, 4)}-${substr(var.env, 0, 3)}${local.hash10}"
  resource_alphanum_name = "${substr(join("", local.resource_suffix), 0, 5)}${substr(var.env, 0, 3)}${local.hash14}"
}
