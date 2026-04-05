# _variables.swa.tf

variable "swa_location" {
  description = <<-EOT
    Azure region for the Static Web App.
    Static Web Apps Free tier is available in a limited set of regions
    (e.g. westus2, centralus, eastus2, westeurope, eastasia, eastasiaapac).
    This may differ from var.location used for other resources.
  EOT
  type        = string
  default     = "eastus2"
}
