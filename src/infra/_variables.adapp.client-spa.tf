# _variables.adapp.client-spa.tf

variable "client_app_display_name" {
  description = "Display name for the SPA client App Registration"
  type        = string
  default     = "demo-client-app"
}

variable "client_app_redirect_uris" {
  description = "List of SPA redirect URIs"
  type        = list(string)
  default = [
    "http://localhost:3000/",
    "http://localhost:5173/",
  ]
}
