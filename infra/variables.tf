variable "environment" {
  type        = string
  description = "Deployment environment name"
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "uat", "prod"], var.environment)
    error_message = "Environment must be dev, staging, uat, or prod"
  }
}

variable "deployment_phase" {
  type        = string
  description = "Deployment phase: bootstrap for ingress/registry, data for PVC setup, app for the full application, or all for one-shot deployment"
  default     = "all"

  validation {
    condition     = contains(["bootstrap", "data", "app", "all"], var.deployment_phase)
    error_message = "deployment_phase must be bootstrap, data, app, or all"
  }
}

variable "kubeconfig_path" {
  type        = string
  description = "Path to kubeconfig file for Kubernetes cluster access"
  default     = "~/.kube/config"
}

variable "kubernetes_namespace" {
  type        = string
  description = "Kubernetes namespace for Aegis Scholar deployment"
  default     = ""
}

variable "create_namespace" {
  type        = bool
  description = "Create the Kubernetes namespace if it does not already exist"
  default     = true
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

variable "helm_release_name" {
  type        = string
  description = "Name of the Helm release for Aegis Scholar"
  default     = "aegis-scholar"
}

variable "helm_chart_path" {
  type        = string
  description = "Path to the Aegis Scholar Helm chart"
  default     = "../k8s/charts/aegis-scholar"
}

variable "values_file" {
  type        = string
  description = "Optional explicit path to a Helm values file. If empty, the environment-specific values file is used."
  default     = ""
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

variable "install_traefik" {
  type        = bool
  description = "Install Traefik ingress controller via Helm"
  default     = true
}

variable "traefik_namespace" {
  type        = string
  description = "Namespace for the Traefik ingress controller"
  default     = "traefik-system"
}

variable "traefik_chart_version" {
  type        = string
  description = "Pinned Traefik chart version for reproducible local deploys"
  default     = "39.0.7"
}

variable "traefik_image_tag" {
  type        = string
  description = "Pinned Traefik image tag for local deploys"
  default     = "v3.6.12"
}

variable "traefik_web_port" {
  type        = number
  description = "Port exposed by Traefik's web entrypoint"
  default     = 80
}

variable "create_registry_config_daemonset" {
  type        = bool
  description = "Install the registry-config DaemonSet used by the local Docker Desktop registry flow"
  default     = false
}

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
