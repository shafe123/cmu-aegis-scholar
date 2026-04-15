output "namespace" {
  description = "Kubernetes namespace where AEGIS Scholar is deployed"
  value       = kubernetes_namespace.aegis_scholar.metadata[0].name
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
