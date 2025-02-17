variable "resource_group_location" {
  type        = string
  description = "Location for all resources."
  default     = "eastus2"
}

variable "resource_group_name" {
  type        = string
  description = "Name of the Resource Group"
  default     = "rg-citimesh"
}

variable "sql_server_name" {
  type = string
  description = "Name of the SQL Server"
  default = "citimesh"
}

variable "sql_db_name" {
  type        = string
  description = "The name of the SQL Database."
  default     = "Resources"
}

variable "admin_username" {
  type        = string
  description = "The administrator username of the SQL logical server."
  default     = "azureadmin"
}

variable "admin_password" {
  type        = string
  description = "The administrator password of the SQL logical server."
  sensitive   = true
  default     = null
}

# AAD Variables
variable "aad_admin_username" {
  type        = string
  description = "The Azure AD admin username for SQL Server."
  default     = "citimesh@rmikulecdevgmail.onmicrosoft.com"
}