terraform {
  required_version = ">= 1.10"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
    random  = { source = "hashicorp/random", version = "~> 3.6" }
  }
}
provider "azurerm" {
  storage_use_azuread             = true
  resource_provider_registrations = "none"
  features {
    resource_group { prevent_deletion_if_contains_resources = false }
  }
}
provider "random" {}
data "azurerm_client_config" "current" {}
variable "ip_operador" {
  type = string
  validation {
    condition     = can(cidrnetmask("${var.ip_operador}/32"))
    error_message = "ip_operador deve ser IPv4."
  }
}
resource "random_string" "sufixo" {
  length  = 5
  lower   = true
  upper   = false
  numeric = true
  special = false
}
resource "azurerm_resource_group" "state" {
  name     = "rg-vigia-chuva-tfstate"
  location = "brazilsouth"
}
resource "azurerm_storage_account" "state" {
  name                            = "stvigiatf${random_string.sufixo.result}"
  resource_group_name             = azurerm_resource_group.state.name
  location                        = azurerm_resource_group.state.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  blob_properties {
    versioning_enabled = true
    delete_retention_policy { days = 7 }
  }
  network_rules {
    default_action = "Deny"
    ip_rules       = [var.ip_operador]
    bypass         = ["AzureServices"]
  }
}
resource "azurerm_role_assignment" "state_writer" {
  scope                = azurerm_storage_account.state.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}
resource "azurerm_storage_container" "state" {
  name                  = "tfstate"
  storage_account_id    = azurerm_storage_account.state.id
  container_access_type = "private"
  depends_on            = [azurerm_role_assignment.state_writer]
}
output "resource_group_name" { value = azurerm_resource_group.state.name }
output "storage_account_name" { value = azurerm_storage_account.state.name }
output "container_name" { value = azurerm_storage_container.state.name }
