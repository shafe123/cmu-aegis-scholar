resource "azurerm_resource_group" "rg" {
  name     = var.resource_group
  location = var.location
}

resource "azurerm_log_analytics_workspace" "law" {
  name                = "aegis-scholar-${var.environment}-logs"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_container_app_environment" "env" {
  name                       = "aegis-scholar-${var.environment}-env"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id
}

resource "azurerm_user_assigned_identity" "acr_pull" {
  name                = "aegis-scholar-${var.environment}-acr-pull"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = var.acr_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.acr_pull.principal_id
}

resource "azurerm_container_app" "vector_db" {
  name                         = "vector-db"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.acr_pull.id]
  }

  registry {
    server   = "${var.acr_base}.azurecr.io"
    identity = azurerm_user_assigned_identity.acr_pull.id
  }

  ingress {
    external_enabled = true
    target_port      = var.target_port
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    container {
      name   = "vector-db"
      image  = "${var.acr_base}.azurecr.io/${var.image_name}:latest"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "MILVUS_HOST"
        value = var.milvus_host
      }

      env {
        name  = "MILVUS_PORT"
        value = var.milvus_port
      }

      env {
        name  = "DEFAULT_COLLECTION"
        value = "aegis_vectors"
      }

      env {
        name  = "EMBEDDING_MODEL_NAME"
        value = "sentence-transformers/all-MiniLM-L6-v2"
      }

      liveness_probe {
        path             = "/health"
        port             = var.target_port
        transport        = "HTTP"
        interval_seconds = 30
        timeout          = 5
        initial_delay    = 60
      }

      readiness_probe {
        path             = "/health"
        port             = var.target_port
        transport        = "HTTP"
        interval_seconds = 30
        timeout          = 5
        initial_delay    = 60
      }
    }
  }
}
