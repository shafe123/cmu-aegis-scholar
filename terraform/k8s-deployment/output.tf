output "namespace" {
  description = "Kubernetes namespace where AEGIS Scholar is deployed"
  value       = local.namespace
}

output "helm_release_name" {
  description = "Name of the Helm release"
  value       = helm_release.aegis_scholar.name
}

output "helm_release_status" {
  description = "Status of the Helm release"
  value       = helm_release.aegis_scholar.status
}

output "helm_release_version" {
  description = "Version of the Helm release"
  value       = helm_release.aegis_scholar.version
}

output "traefik_enabled" {
  description = "Whether Traefik is managed by this module"
  value       = var.install_traefik
}

output "deployment_phase" {
  description = "Current staged deployment phase"
  value       = var.deployment_phase
}
