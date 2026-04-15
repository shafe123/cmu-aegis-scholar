terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~>3.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
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

# Kubernetes provider configuration
# This uses the default kubeconfig or can be configured with specific cluster details
provider "kubernetes" {
  # Option 1: Use default kubeconfig from ~/.kube/config
  config_path = var.kubeconfig_path

  # Option 2: Configure inline (uncomment and configure as needed)
  # host                   = var.kubernetes_host
  # token                  = var.kubernetes_token
  # cluster_ca_certificate = base64decode(var.kubernetes_ca_cert)
  
  # Option 3: For Azure AKS (uncomment if using AKS)
  # host                   = azurerm_kubernetes_cluster.aks[0].kube_config.0.host
  # client_certificate     = base64decode(azurerm_kubernetes_cluster.aks[0].kube_config.0.client_certificate)
  # client_key             = base64decode(azurerm_kubernetes_cluster.aks[0].kube_config.0.client_key)
  # cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.aks[0].kube_config.0.cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    config_path = var.kubeconfig_path
  }
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

module "example_service" {
  source      = "./example-service"
  environment = var.environment
  acr_base    = azurerm_container_registry.aegis_scholar_acr.name
  acr_id      = azurerm_container_registry.aegis_scholar_acr.id
}

module "vector_db" {
  source      = "./vector-db"
  environment = var.environment
  acr_base    = azurerm_container_registry.aegis_scholar_acr.name
  acr_id      = azurerm_container_registry.aegis_scholar_acr.id
}

# Kubernetes Deployment Module (optional - enable when deploying to K8s)
# Uncomment and configure when you want to deploy to a Kubernetes cluster
# module "k8s_deployment" {
#   source = "./k8s-deployment"
#
#   environment         = var.environment
#   kubernetes_namespace = var.kubernetes_namespace
#   helm_release_name   = var.helm_release_name
#   helm_chart_path     = var.helm_chart_path
#   image_registry      = var.image_registry != "" ? var.image_registry : "${azurerm_container_registry.aegis_scholar_acr.login_server}"
#   image_tag           = var.image_tag
#
#   # Secrets (consider using Azure Key Vault or external secret management)
#   neo4j_password      = var.neo4j_password
#   registry_username   = var.registry_username
#   registry_password   = var.registry_password
#   registry_email      = var.registry_email
# }
