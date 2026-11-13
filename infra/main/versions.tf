terraform {
  required_version = ">= 1.10"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
    random  = { source = "hashicorp/random", version = "~> 3.6" }
    time    = { source = "hashicorp/time", version = "~> 0.12" }
  }
  backend "azurerm" {
    key              = "main.tfstate"
    use_azuread_auth = true
  }
}
provider "azurerm" {
  storage_use_azuread = true
  features {
    key_vault { purge_soft_delete_on_destroy = true }
    resource_group { prevent_deletion_if_contains_resources = false }
  }
}
provider "random" {}
provider "time" {}
data "azurerm_client_config" "current" {}
locals { tags = { projeto = var.projeto, gerenciado_por = "terraform" } }
