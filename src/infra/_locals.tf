# _locals.tf

# Naming variables for AI Foundry resources
locals {
  resource_group_name    = "rg-${local.resource_long_name}"
  cognitive_account_name = "cogacct-${local.resource_long_name}"
  cognitive_project_name = "proj-${local.resource_simple_name}"
  acr_name               = "cr${local.resource_alphanum_name}"
  appinsights_name       = "appi-${local.resource_long_name}"

  # Container Apps
  container_apps_env_name      = "cae-${local.resource_long_name}"
  container_apps_identity_name = "uami-ca-acr-${local.resource_long_name}"
  backend_api_identity_name    = "uami-ca-foundry-${local.resource_long_name}"
  log_analytics_workspace_name = "law-${local.resource_long_name}"

  # Static Web App
  swa_name = "swa-${local.resource_long_name}"
}

/*
  Computed environment variables for Container Apps.

  These reference Terraform-managed resources (data sources, azuread_application, etc.)
  and cannot be placed in var.container_apps.env. They are merged with user-supplied
  static env values in local.container_app_env.

  To add env vars for a new app, add an entry keyed by the var.container_apps map key.
*/
locals {
  container_app_computed_env = {
    "identity-echo-api" = {
      ENTRA_TENANT_ID              = data.azurerm_client_config.current.tenant_id
      ENTRA_RESOURCE_API_CLIENT_ID = azuread_application.resource_api.client_id
      FRONTEND_SPA_APP_URL         = "https://${azurerm_static_web_app.frontend.default_host_name}"
    }
    "backend-api" = {
      ENTRA_TENANT_ID          = data.azurerm_client_config.current.tenant_id
      FOUNDRY_PROJECT_ENDPOINT = "${azurerm_cognitive_account.this.endpoint}api/projects/${azurerm_cognitive_account_project.this.name}"
      AZURE_CLIENT_ID          = azurerm_user_assigned_identity.backend_api.client_id
      FRONTEND_SPA_APP_URL     = "https://${azurerm_static_web_app.frontend.default_host_name}"
    }
  }

  # Merge computed env (Terraform references) with user-supplied static env.
  # User-supplied values take precedence (override computed values).
  container_app_env = {
    for k, v in var.container_apps : k => merge(
      lookup(local.container_app_computed_env, k, {}),
      v.env,
    )
  }
}

/*
  Build a clean tags map — merge base tags with non-empty optional tags,
  matching Bicep's union() pattern that omits keys with null values.
*/
locals {
  tags = merge(
    var.tags,
    var.owner != "" ? { owner = var.owner } : {},
    var.cost_center != "" ? { costCenter = var.cost_center } : {},
    var.business_unit != "" ? { businessUnit = var.business_unit } : {},
    var.criticality != "" ? { criticality = var.criticality } : {},
    var.data_classification != "" ? { dataClassification = var.data_classification } : {},
    var.expiry_date != "" ? { expiryDate = var.expiry_date } : {},
  )
}
