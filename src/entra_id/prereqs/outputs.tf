# outputs.tf

output "agent_id_manager_client_id" {
  description = "Agent ID Manager Application (client) ID — set as GRAPH_API_OPS_CLIENT_ID in .env"
  value       = azuread_application.agent_id_manager.client_id
}

output "agent_id_manager_object_id" {
  description = "Agent ID Manager Application Object ID"
  value       = azuread_application.agent_id_manager.object_id
}

output "agent_id_manager_sp_object_id" {
  description = "Agent ID Manager Service Principal (Enterprise App) Object ID"
  value       = azuread_service_principal.agent_id_manager.object_id
}
