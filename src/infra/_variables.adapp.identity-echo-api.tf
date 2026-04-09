# _variables.adapp.identity-echo-api.tf

variable "resource_api_display_name" {
  description = "Display name for the Identity Echo API App Registration"
  type        = string
  default     = "demo-identity-echo-api"
}

variable "resource_api_delegated_scope_name" {
  description = "Delegated permission scope name"
  type        = string
  default     = "CallerIdentity.Read"
}

variable "resource_api_delegated_scope_description" {
  description = "Delegated permission scope description (admin consent)"
  type        = string
  default     = "Read caller identity information from the Identity Echo API"
}

variable "resource_api_app_role_name" {
  description = "Application permission (App Role) value"
  type        = string
  default     = "CallerIdentity.Read.All"
}

variable "resource_api_app_role_description" {
  description = "Application permission description"
  type        = string
  default     = "Read all caller identity information without a signed-in user"
}
