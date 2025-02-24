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




resource "azurerm_service_plan" "citimesh_plan" {
  sku_name = "B1"
  os_type = "Linux"
  name                = "citimesh-app-service-plan"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_container_registry" "citimesh_registry" {
  name                = var.registry_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
}

resource "azurerm_app_service" "citimesh_app" {
  name                = "citimesh-app"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  app_service_plan_id = azurerm_service_plan.citimesh_plan.id

  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    "DOCKER_REGISTRY_SERVER_URL"      = azurerm_container_registry.citimesh_registry.login_server
    "WEBSITES_ENABLE_APP_SERVICE_STORAGE" = "false"
    "OPENAI_API_KEY"                  = data.azurerm_key_vault_secret.openai_api_key.value
    "TWILIO_CODE"                     = data.azurerm_key_vault_secret.twilio_code.value
    "TWILIO_ACCOUNT_SID"              = data.azurerm_key_vault_secret.twilio_account_sid.value
    "TWILIO_ACCOUNT_TOKEN"            = data.azurerm_key_vault_secret.twilio_account_code.value
    "TWILIO_API_KEY"                  = data.azurerm_key_vault_secret.twilio_api_key.value
    "TWILIO_API_SECRET"               = data.azurerm_key_vault_secret.twilio_api_secret.value
    "TWILIO_NUMBER"                   = var.phone_number
    "TWILIO_MESSAGE_SERVICE_SID"      = data.azurerm_key_vault_secret.twilio_message_service_sid.value
    "GOOGLE_MAPS_API"                 = data.azurerm_key_vault_secret.google_maps_api.value
    "SQL_ADMIN_PASSWORD"              = local.admin_password
  }

  site_config {
    linux_fx_version = "DOCKER|${azurerm_container_registry.citimesh_registry.login_server}/${var.image_name}:${var.image_tag}"
    acr_use_managed_identity_credentials = "true"
  }

  depends_on = [azurerm_container_registry.citimesh_registry]
}

resource "azurerm_role_assignment" "acr_pull_role" {
  scope                = azurerm_container_registry.citimesh_registry.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_app_service.citimesh_app.identity[0].principal_id
}