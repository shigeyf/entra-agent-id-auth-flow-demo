# main.swa.tf

/*
  Azure Static Web App for hosting the SPA frontend.

  The SPA (React + Vite) is deployed to Azure Static Web Apps.
  After `terraform apply`, use the deployment token to deploy the built
  frontend via `swa deploy` CLI or CI/CD pipeline:

    cd src/frontend
    npm run build
    npx @azure/static-web-apps-cli deploy dist \
      --deployment-token <swa_deployment_token output>
*/

resource "azurerm_static_web_app" "frontend" {
  name                = local.swa_name
  resource_group_name = azurerm_resource_group.this.name
  location            = var.swa_location
  tags                = local.tags

  sku_tier = "Free"
  sku_size = "Free"
}
