# main.cognitive.seed-agent.tf

/*
  Seed Agent: Bootstrap agentIdentity on the Foundry Project.

  The Project's properties.agentIdentity (Blueprint + Agent Identity) is only
  populated after the first agent is created via the Foundry Agent Service
  Data Plane API.  This resource creates a minimal Declarative Agent
  (kind: "prompt") — which requires no container image — and then immediately
  deletes it.  The agentIdentity persists on the Project after deletion.

  REST API details (from azure-ai-projects SDK source):
    POST /agents/{name}/versions?api-version=v1   — create version
    DELETE /agents/{name}?api-version=v1           — delete agent

  Prerequisites:
    - Capability Host must be provisioned first
    - At least one model deployment must exist
    - Terraform executor must have Azure AI User role on the Project
*/

resource "terraform_data" "seed_agent" {
  depends_on = [
    azurerm_cognitive_account_project.this,
    azapi_resource.capability_host,
    azurerm_cognitive_deployment.models,
  ]

  triggers_replace = azurerm_cognitive_account_project.this.id

  provisioner "local-exec" {
    # Cross-platform: Use python command directly
    working_dir = path.module
    command     = "python scripts/seed-agent.py ${azurerm_cognitive_account.this.endpoint} ${azurerm_cognitive_account_project.this.name} ${local.inference_deployments[0].name}"
  }
}
