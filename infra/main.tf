terraform {
  required_providers {
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

provider "kubernetes" {
  config_path = pathexpand(var.kubeconfig_path)
}

provider "helm" {
  kubernetes {
    config_path = pathexpand(var.kubeconfig_path)
  }
}

module "k8s_deployment" {
  source = "./k8s-deployment"

  environment                       = var.environment
  kubernetes_namespace              = var.kubernetes_namespace
  create_namespace                  = var.create_namespace
  helm_release_name                 = var.helm_release_name
  helm_chart_path                   = var.helm_chart_path
  values_file                       = var.values_file
  image_registry                    = var.image_registry
  image_tag                         = var.image_tag
  install_traefik                   = var.install_traefik
  traefik_namespace                 = var.traefik_namespace
  traefik_web_port                  = var.traefik_web_port
  create_registry_config_daemonset  = var.create_registry_config_daemonset

  neo4j_password    = var.neo4j_password
  registry_username = var.registry_username
  registry_password = var.registry_password
  registry_email    = var.registry_email
}
