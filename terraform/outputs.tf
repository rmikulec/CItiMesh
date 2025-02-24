output "resource_group_name" {
  value = azurerm_resource_group.rg.name
}

output "sql_server_name" {
  value = azurerm_mssql_server.server.name
}


output "admin_password" {
  sensitive = true
  value     = local.admin_password
}

output "aad_admin" {
  value = var.aad_admin_username
}

output "app_service_url" {
  description = "The URL of the deployed FastAPI app"
  value       = azurerm_app_service.citimesh_app.default_site_hostname
}