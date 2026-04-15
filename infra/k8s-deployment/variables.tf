variable "environment" {
  type        = string
  description = "Deployment environment (dev, staging, prod)"
}

variable "kubernetes_namespace" {
  type        = string
  description = "Kubernetes namespace for deployment"
  default     = ""
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

variable "neo4j_password" {
  type        = string
  description = "Neo4j database password"
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
