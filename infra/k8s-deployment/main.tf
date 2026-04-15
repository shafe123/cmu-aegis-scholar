# Kubernetes Deployment Module for AEGIS Scholar
# This module deploys the AEGIS Scholar application to a Kubernetes cluster using Helm

locals {
  namespace  = var.kubernetes_namespace != "" ? var.kubernetes_namespace : "aegis-${var.environment}"
  chart_path = var.helm_chart_path
}

# Create namespace if it doesn't exist
resource "kubernetes_namespace" "aegis_scholar" {
  metadata {
    name = local.namespace
    labels = {
      name        = local.namespace
      environment = var.environment
      managed-by  = "terraform"
    }
  }
}

# Create Neo4j authentication secret
resource "kubernetes_secret" "neo4j_auth" {
  metadata {
    name      = "neo4j-auth"
    namespace = kubernetes_namespace.aegis_scholar.metadata[0].name
  }

  data = {
    NEO4J_AUTH_USER     = "neo4j"
    NEO4J_AUTH_PASSWORD = var.neo4j_password
    NEO4J_AUTH          = "neo4j/${var.neo4j_password}"
  }

  type = "Opaque"
}

# Create image pull secret if registry credentials are provided
resource "kubernetes_secret" "registry_credentials" {
  count = var.registry_username != "" && var.registry_password != "" ? 1 : 0

  metadata {
    name      = "registry-credentials"
    namespace = kubernetes_namespace.aegis_scholar.metadata[0].name
  }

  type = "kubernetes.io/dockerconfigjson"

  data = {
    ".dockerconfigjson" = jsonencode({
      auths = {
        (var.image_registry) = {
          username = var.registry_username
          password = var.registry_password
          email    = var.registry_email
          auth     = base64encode("${var.registry_username}:${var.registry_password}")
        }
      }
    })
  }
}

# Deploy AEGIS Scholar using Helm
resource "helm_release" "aegis_scholar" {
  name      = var.helm_release_name
  namespace = kubernetes_namespace.aegis_scholar.metadata[0].name
  chart     = local.chart_path
  timeout   = 600
  wait      = true

  # Use environment-specific values file
  values = [
    file("${local.chart_path}/values-${var.environment}.yaml")
  ]

  # Override specific values
  set {
    name  = "global.imageRegistry"
    value = var.image_registry
  }

  set {
    name  = "global.namespace"
    value = local.namespace
  }

  dynamic "set" {
    for_each = var.registry_username != "" ? [1] : []
    content {
      name  = "global.imagePullSecrets[0].name"
      value = "registry-credentials"
    }
  }

  set {
    name  = "aegis-scholar-api.image.tag"
    value = var.image_tag
  }

  set {
    name  = "vector-db.image.tag"
    value = var.image_tag
  }

  set {
    name  = "graph-db.image.tag"
    value = var.image_tag
  }

  # Milvus configuration
  set {
    name  = "milvus.enabled"
    value = "true"
  }

  # Neo4j configuration
  set {
    name  = "graph-db.neo4j.enabled"
    value = "true"
  }

  depends_on = [
    kubernetes_secret.neo4j_auth,
    kubernetes_secret.registry_credentials
  ]
}
