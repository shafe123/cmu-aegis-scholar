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
}

provider "azurerm" {
  features {}
}

# Kubernetes provider configuration
# This uses the default kubeconfig or can be configured with specific cluster details
provider "kubernetes" {
  # Option 1: Use default kubeconfig from ~/.kube/config
  config_path = var.kubeconfig_path
}

provider "helm" {
  kubernetes {
    config_path = var.kubeconfig_path
  }
}

module "k8s_deployment" {
  source = "./k8s-deployment"

  environment          = var.environment
  kubernetes_namespace = var.kubernetes_namespace
  helm_release_name    = var.helm_release_name
  helm_chart_path      = var.helm_chart_path
  image_registry       = var.image_registry
  image_tag            = var.image_tag

  # Secrets (consider using Azure Key Vault or external secret management)
  neo4j_password    = var.neo4j_password
  registry_username = var.registry_username
  registry_password = var.registry_password
  registry_email    = var.registry_email
}
