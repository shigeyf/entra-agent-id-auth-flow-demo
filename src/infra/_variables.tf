# _variables.tf

variable "tenant_id" {
  description = "Entra ID tenant identifier (GUID)"
  type        = string
  default     = ""

  validation {
    condition = (
      var.tenant_id == ""
      || can(regex(
        "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        var.tenant_id,
      ))
    )
    error_message = "Entra ID tenant identifier must be a valid GUID"
  }
}

variable "target_subscription_id" {
  description = "Azure Subscription Id for the bootstrap resources. Leave empty to use the az login subscription"
  type        = string
  default     = ""

  validation {
    condition = (
      var.target_subscription_id == ""
      || can(regex(
        "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        var.target_subscription_id,
      ))
    )
    error_message = "Azure subscription id must be a valid GUID"
  }
}

variable "naming_suffix" {
  description = "Naming suffix for the deployed resources"
  type        = list(string)
  default     = ["foundry", "poc"]
}

variable "env" {
  description = "Environment tag value for the deployed resources"
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region for the deployment"
  type        = string
}

variable "tags" {
  description = "Tags for the deployment"
  type        = map(string)
  default = {
    env     = "dev"
    project = "foundry"
    purpose = "poc"
  }
}

variable "is_production" {
  description = "Flag to indicate if this is a production environment. When false (demo/dev), resources will be completely purged on destroy for clean teardown. When true (production), resources will be soft-deleted to prevent accidental data loss."
  type        = bool
  default     = false
}
