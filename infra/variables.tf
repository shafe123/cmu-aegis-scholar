variable "location" {
  type        = string
  description = "The azure region to deploy to"
  default     = "eastus"
}

variable "resource_group_terraform" {
  type        = string
  description = "The resource group that stores the terraform state files"
  default     = "aegis_scholar_essential"
}

variable "storage_account_terraform" {
  type        = string
  description = "The storage account name that stores the terraform state files"
  default     = "aegisscholarterraform"
}

variable "acr_base_name" {
  type        = string
  description = "The name of the ACR for base images"
  default     = "aegisscholarbase"
}

variable "environment" {
  type        = string
  description = "Deployment environment name"
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "uat", "prod"], var.environment)
    error_message = "Environment must be dev, staging, uat, or prod"
  }
}

# Kubernetes Configuration Variables
variable "kubeconfig_path" {
  type        = string
  description = "Path to kubeconfig file for Kubernetes cluster access"
  default     = "~/.kube/config"
}

variable "kubernetes_namespace" {
  type        = string
  description = "Kubernetes namespace for AEGIS Scholar deployment"
  default     = "" # Will default to aegis-{environment}
}

variable "kubernetes_host" {
  type        = string
  description = "Kubernetes cluster API server endpoint (optional, if not using kubeconfig)"
  default     = ""
  sensitive   = true
}

variable "kubernetes_token" {
  type        = string
  description = "Kubernetes authentication token (optional, if not using kubeconfig)"
  default     = ""
  sensitive   = true
}

variable "kubernetes_ca_cert" {
  type        = string
  description = "Kubernetes cluster CA certificate base64 encoded (optional, if not using kubeconfig)"
  default     = ""
  sensitive   = true
}

# Helm Configuration Variables
variable "helm_release_name" {
  type        = string
  description = "Name of the Helm release for AEGIS Scholar"
  default     = "aegis-scholar"
}

variable "helm_chart_path" {
  type        = string
  description = "Path to the AEGIS Scholar Helm chart"
  default     = "../k8s/charts/aegis-scholar"
}

variable "image_registry" {
  type        = string
  description = "Container image registry URL"
  default     = ""
}

variable "image_tag" {
  type        = string
  description = "Container image tag to deploy"
  default     = "latest"
}

# Secrets (use with caution - prefer environment variables or secret management systems)
variable "neo4j_password" {
  type        = string
  description = "Neo4j database password"
  default     = ""
  sensitive   = true
}

variable "registry_username" {
  type        = string
  description = "Container registry username"
  default     = ""
  sensitive   = true
}

variable "registry_password" {
  type        = string
  description = "Container registry password"
  default     = ""
  sensitive   = true
}

variable "registry_email" {
  type        = string
  description = "Container registry email"
  default     = ""
}
