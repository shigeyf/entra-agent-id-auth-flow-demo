# _variables.containerapp.tf

variable "container_apps" {
  description = <<-EOT
    Map of Container Apps to deploy in the shared Container Apps Environment.
    Each key becomes part of the resource name: ca-{key}-{suffix}.

    Example:
      container_apps = {
        "identity-echo-api" = {
          image_name    = "identity-echo-api"
          target_port   = 8000
          build_context = "../../identity_echo_api"
        }
      }
  EOT

  type = map(object({
    image_name    = string
    image_tag     = optional(string, "latest")
    target_port   = number
    cpu           = optional(number, 0.25)
    memory        = optional(string, "0.5Gi")
    min_replicas  = optional(number, 0)
    max_replicas  = optional(number, 1)
    external      = optional(bool, true)
    env           = optional(map(string), {})
    build_context = optional(string, "") # Relative path from this module to the Docker build context
    dockerfile    = optional(string, "Dockerfile")
  }))

  default = {}

  validation {
    condition = alltrue([
      for k, _ in var.container_apps : length(k) <= 22
    ])
    error_message = "Container App map keys must be 22 characters or fewer (32 char limit minus 'ca-' prefix and '-hash6' suffix)."
  }
}
