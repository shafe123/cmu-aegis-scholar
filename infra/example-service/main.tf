resource "azurerm_resource_group" "example_service" {
  name     = var.resource_group
  location = var.location

  lifecycle {
    prevent_destroy = true
  }
  tags = { "env" : var.environment }
}

resource "azurerm_log_analytics_workspace" "example_service" {
  name                = "lawexampleservice"
  location            = azurerm_resource_group.example_service.location
  resource_group_name = azurerm_resource_group.example_service.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = { "env" : var.environment }
}

resource "azurerm_container_app_environment" "example_serivce" {
  name                       = "envexampleservice"
  location                   = azurerm_resource_group.example_service.location
  resource_group_name        = azurerm_resource_group.example_service.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.example_service.id
  tags                       = { "env" : var.environment }
}

resource "azurerm_user_assigned_identity" "acrpull_identity" {
  name                = "identityexampleserviceacrpull"
  resource_group_name = var.resource_group
  location            = var.location
}

resource "azurerm_role_assignment" "acr_pull" { # needed to pull images for the container app
  principal_id         = azurerm_user_assigned_identity.acrpull_identity.principal_id
  role_definition_name = "AcrPull"
  scope                = var.acr_id
}

resource "azurerm_container_app" "example_service" {
  name                         = "appexampleservice"
  container_app_environment_id = azurerm_container_app_environment.example_serivce.id
  resource_group_name          = azurerm_resource_group.example_service.name
  revision_mode                = "Single"
  ingress {
    target_port      = var.target_port
    external_enabled = true
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.acrpull_identity.id]
  }

  registry {
    server   = "${var.acr_base}.azurecr.io"
    identity = azurerm_user_assigned_identity.acrpull_identity.id
  }

  template {
    container {
      name   = "exampleserviceapp"
      image  = "${var.acr_base}.azurecr.io/${var.image_name}:latest"
      cpu    = 0.25
      memory = "0.5Gi"
    }
  }
  tags = { "env" : var.environment }
}

