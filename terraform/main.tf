resource "azurerm_resource_group" "rg" {
  name     = "${var.resource_group_name}-${terraform.workspace}"
  location = var.resource_group_location
}

resource "random_password" "admin_password" {
  count       = var.admin_password == null ? 1 : 0
  length      = 20
  special     = false
  min_numeric = 1
  min_upper   = 1
  min_lower   = 1
  min_special = 0
}

locals {
  admin_password = try(random_password.admin_password[0].result, var.admin_password)
}

resource "azurerm_mssql_server" "server" {
  name                         = "${var.sql_server_name}-${terraform.workspace}"
  resource_group_name          = azurerm_resource_group.rg.name
  location                     = azurerm_resource_group.rg.location
  administrator_login          = var.admin_username
  administrator_login_password = local.admin_password
  version                      = "12.0"

  azuread_administrator {
    login_username     = var.aad_admin_username
    object_id = data.azuread_user.aad_admin_user.object_id
    tenant_id = data.azurerm_client_config.current.tenant_id
  }
}

# AAD Administrator Setup
data "azurerm_client_config" "current" {}

data "azuread_user" "aad_admin_user" {
  user_principal_name = var.aad_admin_username
}

resource "azurerm_mssql_database" "db" {
  name      = var.sql_db_name
  server_id = azurerm_mssql_server.server.id
  collation           = "SQL_Latin1_General_CP1_CI_AS"
  max_size_gb         = 10
  sku_name            = "GP_S_Gen5_2" # General Purpose, Gen5, 2 vCores
  zone_redundant      = false
  min_capacity                 = 0.5  # Minimum 0.5 vCores
  auto_pause_delay_in_minutes  = 60   # Set between 60 and 10080 minutes, or -1 to disable
}

# For access through internet
resource "azurerm_mssql_firewall_rule" "block_public_access" {
  name                = "block-public-access"
  server_id = azurerm_mssql_server.server.id
  start_ip_address    = "0.0.0.0"
  end_ip_address      = "0.0.0.0"
}

# Firewall Rule for Power BI Service
resource "azurerm_mssql_firewall_rule" "allow_power_bi_service" {
  name                = "allow-powerbi-service"
  server_id           = azurerm_mssql_server.server.id
  start_ip_address    = "13.66.0.0"  # Example IP range for Power BI service
  end_ip_address      = "13.67.255.255"
}
