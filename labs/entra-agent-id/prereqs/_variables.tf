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

variable "app_display_name" {
  description = "Display name for the Agent ID Manager App Registration"
  type        = string
  default     = "Entra-Agent-ID-Manager"
}

variable "app_role_assignment_required" {
  description = "Whether user assignment is required on the Enterprise Application. When true, only assigned users/groups can obtain tokens."
  type        = bool
  default     = true
}

variable "assigned_user_object_ids" {
  description = "List of Entra ID user object IDs to assign to the Enterprise Application (only effective when app_role_assignment_required = true)"
  type        = list(string)
  default     = []
}

variable "assigned_group_object_ids" {
  description = "List of Entra ID group object IDs to assign to the Enterprise Application (only effective when app_role_assignment_required = true)"
  type        = list(string)
  default     = []
}
