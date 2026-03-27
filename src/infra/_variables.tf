// _variables.tf

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
