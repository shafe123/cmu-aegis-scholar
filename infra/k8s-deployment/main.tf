# Kubernetes Deployment Module for AEGIS Scholar
# This module recreates the current local Helm-based Kubernetes stack in Terraform.

locals {
  namespace              = var.kubernetes_namespace != "" ? var.kubernetes_namespace : "aegis-${var.environment}"
  chart_path             = abspath(var.helm_chart_path)
  values_file            = var.values_file != "" ? abspath(var.values_file) : "${local.chart_path}/values-${var.environment}.yaml"
  phase                  = lower(var.deployment_phase)
  deploy_data_layer      = contains(["data", "app", "all"], local.phase)
  deploy_app_layer       = contains(["app", "all"], local.phase)
  deploy_registry_layer  = contains(["bootstrap", "data", "app", "all"], local.phase)
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
  version          = var.traefik_chart_version
  namespace        = var.traefik_namespace
  create_namespace = true
  wait             = true
  timeout          = 600

  set {
    name  = "image.tag"
    value = var.traefik_image_tag
  }

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
  timeout           = local.deploy_app_layer ? 600 : 120
  wait              = local.deploy_app_layer

  lifecycle {
    precondition {
      condition     = !local.deploy_app_layer || trimspace(var.neo4j_password) != ""
      error_message = "neo4j_password must be set before running the app or all deployment phase. In PowerShell, set $env:TF_VAR_neo4j_password in the same terminal where you run terraform apply."
    }
  }

  values = [
    file(local.values_file)
  ]

  set {
    name  = "global.namespace"
    value = local.namespace
  }

  set {
    name  = "dticData.enabled"
    value = local.deploy_data_layer ? "true" : "false"
  }

  set {
    name  = "docker-registry.enabled"
    value = local.deploy_registry_layer ? "true" : "false"
  }

  set {
    name  = "ingress.enabled"
    value = local.deploy_app_layer ? "true" : "false"
  }

  set {
    name  = "frontend.enabled"
    value = local.deploy_app_layer ? "true" : "false"
  }

  set {
    name  = "aegis-scholar-api.enabled"
    value = local.deploy_app_layer ? "true" : "false"
  }

  set {
    name  = "vector-db.enabled"
    value = local.deploy_app_layer ? "true" : "false"
  }

  set {
    name  = "vector-db.loader.enabled"
    value = local.deploy_app_layer ? "true" : "false"
  }

  set {
    name  = "graph-db.enabled"
    value = local.deploy_app_layer ? "true" : "false"
  }

  set {
    name  = "graph-db.loader.enabled"
    value = local.deploy_app_layer ? "true" : "false"
  }

  set {
    name  = "milvus.enabled"
    value = local.deploy_app_layer ? "true" : "false"
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
                "-ec",
                "REG_DIR=/host/etc/containerd/certs.d/aegis-scholar-docker-registry.${local.namespace}.svc.cluster.local; mkdir -p \"$REG_DIR\"; printf 'server = \"http://localhost:5000\"\\n\\n[host.\"http://localhost:5000\"]\\n  capabilities = [\"pull\", \"resolve\"]\\n  skip_verify = true\\n' > \"$REG_DIR/hosts.toml\"; nsenter --target 1 --mount --uts --ipc --net --pid -- sh -c 'systemctl restart containerd || true'; cat \"$REG_DIR/hosts.toml\""
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

resource "terraform_data" "destroy_service_finalizer_cleanup" {
  input = local.namespace

  depends_on = [
    helm_release.aegis_scholar,
    kubernetes_manifest.registry_config,
  ]

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["PowerShell", "-Command"]
    command     = <<-EOT
      $ns = "${self.input}"
      $ErrorActionPreference = "SilentlyContinue"
      kubectl get svc -n $ns -o name 2>$null | ForEach-Object {
        kubectl patch $_ -n $ns -p '{"metadata":{"finalizers":[]}}' --type=merge 2>$null | Out-Null
      }
    EOT
  }
}
