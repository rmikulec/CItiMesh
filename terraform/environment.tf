data "azurerm_key_vault" "citimesh_keyvault" {
  name                = var.key_vault_name
  resource_group_name = azurerm_resource_group.rg.name
}

data "azurerm_key_vault_secret" "openai_api_key" {
  name         = "openai-api-key"
  key_vault_id = data.azurerm_key_vault.citimesh_keyvault.id
}

data "azurerm_key_vault_secret" "google_maps_api" {
  name         = "google-maps-api"
  key_vault_id = data.azurerm_key_vault.citimesh_keyvault.id
}

data "azurerm_key_vault_secret" "twilio_message_service_sid" {
  name         = "twilio-message-service-sid"
  key_vault_id = data.azurerm_key_vault.citimesh_keyvault.id
}

data "azurerm_key_vault_secret" "twilio_api_secret" {
  name         = "twilio-api-secret"
  key_vault_id = data.azurerm_key_vault.citimesh_keyvault.id
}

data "azurerm_key_vault_secret" "twilio_api_key" {
  name         = "twilio-api-key"
  key_vault_id = data.azurerm_key_vault.citimesh_keyvault.id
}

data "azurerm_key_vault_secret" "twilio_account_sid" {
  name         = "twilio-account-sid"
  key_vault_id = data.azurerm_key_vault.citimesh_keyvault.id
}

data "azurerm_key_vault_secret" "twilio_auth_token" {
  name         = "twilio-auth-token"
  key_vault_id = data.azurerm_key_vault.citimesh_keyvault.id
}
