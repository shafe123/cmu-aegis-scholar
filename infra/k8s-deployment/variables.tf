variable "environment" {
  type        = string
  description = "Deployment environment (dev, staging, prod)"
}

variable "deployment_phase" {
  type        = string
  description = "Deployment phase for staged applies: bootstrap, data, app, or all"
  default     = "all"
}

variable "kubernetes_namespace" {
  type        = string
  description = "Kubernetes namespace for deployment"
  default     = ""
}

variable "create_namespace" {
  type        = bool
  description = "Create the namespace before installing Helm releases"
  default     = true
}

variable "helm_release_name" {
  type        = string
  description = "Name of the Helm release"
  default     = "aegis-scholar"
}

variable "helm_chart_path" {
  type        = string
  description = "Path to the Helm chart"
}

variable "values_file" {
  type        = string
  description = "Optional path to a specific Helm values file"
  default     = ""
}

variable "image_registry" {
  type        = string
  description = "Container image registry"
  default     = ""
}

variable "image_tag" {
  type        = string
  description = "Container image tag"
  default     = "latest"
}

variable "install_traefik" {
  type        = bool
  description = "Install Traefik ingress controller"
  default     = true
}

variable "traefik_namespace" {
  type        = string
  description = "Namespace for the Traefik ingress controller"
  default     = "traefik-system"
}

variable "traefik_web_port" {
  type        = number
  description = "Port for Traefik's web entrypoint"
  default     = 80
}

variable "create_registry_config_daemonset" {
  type        = bool
  description = "Install the registry helper DaemonSet for the local Docker Desktop registry flow"
  default     = false
}

variable "neo4j_password" {
  type        = string
  description = "Neo4j database password"
  sensitive   = true
  default     = ""
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
