# Kubernetes Deployment Module for AEGIS Scholar
# This module recreates the current local Helm-based Kubernetes stack in Terraform.

locals {
  namespace   = var.kubernetes_namespace != "" ? var.kubernetes_namespace : "aegis-${var.environment}"
  chart_path  = abspath(var.helm_chart_path)
  values_file = var.values_file != "" ? abspath(var.values_file) : "${local.chart_path}/values-${var.environment}.yaml"
}

resource "kubernetes_namespace" "aegis_scholar" {
  count = var.create_namespace ? 1 : 0

  metadata {
    name = local.namespace
    labels = {
      name        = local.namespace
      environment = var.environment
      managed-by  = "terraform"
    }
  }
}

resource "kubernetes_secret" "neo4j_auth" {
  count = var.neo4j_password != "" ? 1 : 0

  metadata {
    name      = "neo4j-auth"
    namespace = local.namespace
  }

  data = {
    NEO4J_AUTH_USER     = "neo4j"
    NEO4J_AUTH_PASSWORD = var.neo4j_password
    NEO4J_AUTH          = "neo4j/${var.neo4j_password}"
  }

  type = "Opaque"

  depends_on = [kubernetes_namespace.aegis_scholar]
}

resource "kubernetes_secret" "registry_credentials" {
  count = var.registry_username != "" && var.registry_password != "" && var.image_registry != "" ? 1 : 0

  metadata {
    name      = "registry-credentials"
    namespace = local.namespace
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

  depends_on = [kubernetes_namespace.aegis_scholar]
}

resource "helm_release" "traefik" {
  count = var.install_traefik ? 1 : 0

  name             = "traefik"
  repository       = "https://traefik.github.io/charts"
  chart            = "traefik"
  namespace        = var.traefik_namespace
  create_namespace = true
  wait             = true
  timeout          = 600

  set {
    name  = "ports.web.port"
    value = tostring(var.traefik_web_port)
  }
}

resource "helm_release" "aegis_scholar" {
  name              = var.helm_release_name
  namespace         = local.namespace
  chart             = local.chart_path
  dependency_update = true
  cleanup_on_fail   = true
  timeout           = 600
  wait              = true

  values = [
    file(local.values_file)
  ]

  set {
    name  = "global.namespace"
    value = local.namespace
  }

  dynamic "set" {
    for_each = var.image_registry != "" ? [1] : []
    content {
      name  = "global.imageRegistry"
      value = var.image_registry
    }
  }

  dynamic "set" {
    for_each = var.registry_username != "" && var.registry_password != "" && var.image_registry != "" ? [1] : []
    content {
      name  = "global.imagePullSecrets[0].name"
      value = "registry-credentials"
    }
  }

  set {
    name  = "frontend.image.tag"
    value = var.image_tag
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
    name  = "vector-db.loader.image.tag"
    value = var.image_tag
  }

  set {
    name  = "graph-db.image.tag"
    value = var.image_tag
  }

  set {
    name  = "graph-db.loader.image.tag"
    value = var.image_tag
  }

  depends_on = [
    kubernetes_namespace.aegis_scholar,
    kubernetes_secret.neo4j_auth,
    kubernetes_secret.registry_credentials,
    helm_release.traefik
  ]
}

resource "kubernetes_manifest" "registry_config" {
  count = var.create_registry_config_daemonset ? 1 : 0

  manifest = {
    apiVersion = "apps/v1"
    kind       = "DaemonSet"
    metadata = {
      name      = "registry-config"
      namespace = local.namespace
    }
    spec = {
      selector = {
        matchLabels = {
          name = "registry-config"
        }
      }
      template = {
        metadata = {
          labels = {
            name = "registry-config"
          }
        }
        spec = {
          hostPID     = true
          hostNetwork = true
          initContainers = [
            {
              name  = "configure-containerd"
              image = "alpine:latest"
              command = [
                "sh",
                "-c",
                <<-EOT
                  set -ex
                  mkdir -p /host/etc/containerd/certs.d/aegis-scholar-docker-registry.${local.namespace}.svc.cluster.local
                  cat > /host/etc/containerd/certs.d/aegis-scholar-docker-registry.${local.namespace}.svc.cluster.local/hosts.toml <<EOF
                  server = "http://localhost:5000"

                  [host."http://localhost:5000"]
                    capabilities = ["pull", "resolve"]
                    skip_verify = true
                  EOF
                  nsenter --target 1 --mount --uts --ipc --net --pid -- systemctl restart containerd || true
                EOT
              ]
              securityContext = {
                privileged = true
              }
              volumeMounts = [
                {
                  name      = "host-root"
                  mountPath = "/host"
                }
              ]
            }
          ]
          containers = [
            {
              name    = "sleep"
              image   = "alpine:latest"
              command = ["sleep", "infinity"]
            }
          ]
          volumes = [
            {
              name = "host-root"
              hostPath = {
                path = "/"
              }
            }
          ]
        }
      }
    }
  }

  depends_on = [helm_release.aegis_scholar]
}
