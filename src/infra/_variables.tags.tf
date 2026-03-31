# _variables.tags.tf

/*
  Optional tag parameters (omit or set to "" to leave unset)
*/

variable "owner" {
  description = "Responsible team or owner (e.g., platform-team)"
  type        = string
  default     = ""
}

variable "cost_center" {
  description = "Cost center or chargeback code (e.g., CC-1234)"
  type        = string
  default     = ""
}

variable "business_unit" {
  description = "Business unit or department (e.g., engineering)"
  type        = string
  default     = ""
}

variable "criticality" {
  description = "Business criticality: low | medium | high | critical"
  type        = string
  default     = ""

  validation {
    condition     = var.criticality == "" || contains(["low", "medium", "high", "critical"], var.criticality)
    error_message = "criticality must be one of: low, medium, high, critical (or empty to omit)."
  }
}

variable "data_classification" {
  description = "Data classification: public | internal | confidential | restricted"
  type        = string
  default     = ""

  validation {
    condition     = var.data_classification == "" || contains(["public", "internal", "confidential", "restricted"], var.data_classification)
    error_message = "data_classification must be one of: public, internal, confidential, restricted (or empty to omit)."
  }
}

variable "expiry_date" {
  description = "Scheduled decommission date for temporary resources (ISO 8601, e.g., 2026-12-31)"
  type        = string
  default     = ""
}
