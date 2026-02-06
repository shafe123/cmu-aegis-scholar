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
