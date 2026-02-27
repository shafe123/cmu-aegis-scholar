output "app_url" {
  value = "https://${azurerm_container_app.vector_db.ingress[0].fqdn}"
}

output "app_ip" {
  value = join(",", azurerm_container_app.vector_db.outbound_ip_addresses)
}
