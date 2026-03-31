# .tflint.hcl

plugin "terraform" {
  enabled = true
}

plugin "azurerm" {
  enabled = true
  version = "0.31.1"
  source  = "github.com/terraform-linters/tflint-ruleset-azurerm"
}

rule "terraform_standard_module_structure" {
  enabled = false
}
