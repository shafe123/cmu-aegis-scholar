variable "resource_group" {
  type        = string
  description = "The resource group resources will be deployed to"
  default     = "aegis_scholar_dev"
}

variable "location" {
  type        = string
  description = "The azure region to deploy to"
  default     = "eastus"
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

variable "acr_id" {
  type        = string
  description = "The ID from the base ACR"
}

variable "acr_base" {
  type        = string
  description = "The base name for the ACR"
}

variable "image_name" {
  type        = string
  description = "The image name to deploy for example service"
  default     = "example-service"
}

variable "target_port" {
  type        = number
  description = "The port on the container to map for external connections"
  default     = 8001
}
