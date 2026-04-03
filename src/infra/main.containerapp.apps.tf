# main.containerapp.apps.tf

/*
  Container Apps — deployed from var.container_apps.

  Each entry in var.container_apps creates:
    - An azurerm_container_app resource
    - AcrPull RBAC (via main.rbac.services.tf)

  App-specific environment variables that reference Terraform resources
  (e.g. tenant_id, client_id) are defined in local.container_app_computed_env
  (_locals.tf) and merged with user-supplied static env from var.container_apps[].env.

  Image is pulled from the existing ACR (main.acr.tf) using a User-Assigned MI.
*/

# ---------------------------------------------------------------------------
# Initial container image build — runs `az acr build` for each app that
# specifies a build_context.  Only fires on first apply (or when the
# build_context / dockerfile / image_tag changes).
# ---------------------------------------------------------------------------
resource "null_resource" "acr_build" {
  for_each = {
    for k, v in var.container_apps : k => v if v.build_context != ""
  }

  triggers = {
    build_context = each.value.build_context
    dockerfile    = each.value.dockerfile
    image_tag     = each.value.image_tag
    acr_name      = azurerm_container_registry.this.name
  }

  provisioner "local-exec" {
    command = <<-EOT
      az acr build \
        --registry ${azurerm_container_registry.this.name} \
        --image ${each.value.image_name}:${each.value.image_tag} \
        --file ${each.value.build_context}/${each.value.dockerfile} \
        ${each.value.build_context}
    EOT
  }

  depends_on = [azurerm_container_registry.this]
}

# Wait for RBAC propagation before Container App creation.
# Azure role assignments can take up to 2-3 minutes to propagate.
resource "time_sleep" "wait_for_acr_rbac" {
  create_duration = "60s"

  depends_on = [azurerm_role_assignment.acr_for_container_apps]
}

resource "azurerm_container_app" "apps" {
  for_each = var.container_apps

  name                         = "ca-${each.key}-${local.hash6}"
  resource_group_name          = azurerm_resource_group.this.name
  container_app_environment_id = azurerm_container_app_environment.this.id
  tags                         = local.tags

  revision_mode = "Single"

  registry {
    server   = azurerm_container_registry.this.login_server
    identity = azurerm_user_assigned_identity.container_apps.id
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_apps.id]
  }

  template {
    min_replicas = each.value.min_replicas
    max_replicas = each.value.max_replicas

    container {
      name   = each.key
      image  = "${azurerm_container_registry.this.login_server}/${each.value.image_name}:${each.value.image_tag}"
      cpu    = each.value.cpu
      memory = each.value.memory

      dynamic "env" {
        for_each = local.container_app_env[each.key]
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  ingress {
    external_enabled = each.value.external
    target_port      = each.value.target_port
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  # Ensure AcrPull RBAC has propagated and image exists before the first pull
  depends_on = [
    time_sleep.wait_for_acr_rbac,
    null_resource.acr_build,
  ]
}
