terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~>3.0"
    }
  }
  backend "azurerm" {
    resource_group_name  = "aegis_scholar_essential"
    storage_account_name = "aegisscholarterraform"
    container_name       = "tfstate"
    key                  = "terraform.tfstate"
  }

}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_provider_registration" "app" {
  name = "Microsoft.App"
}

resource "azurerm_resource_group" "aegis_scholar_essential" {
  name     = "aegis_scholar_essential"
  location = var.location

  lifecycle {
    prevent_destroy = true
  }
  tags = { "env" : "required" }
}

resource "random_string" "acr_suffix" {
  length  = 12
  lower   = true
  numeric = true
  special = false
  upper   = false
}

resource "azurerm_container_registry" "aegis_scholar_acr" {
  name                = "${var.acr_base_name}${random_string.acr_suffix.result}"
  location            = azurerm_resource_group.aegis_scholar_essential.location
  resource_group_name = azurerm_resource_group.aegis_scholar_essential.name
  sku                 = "Basic"

  lifecycle {
    prevent_destroy = true
  }
  tags = { "env" : "required" }
}

module "example_serivce" {
  source      = "./example-service"
  environment = var.environment
  acr_base    = azurerm_container_registry.aegis_scholar_acr.name
  acr_id      = azurerm_container_registry.aegis_scholar_acr.id
}
