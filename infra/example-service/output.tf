output "app_url" {
  value = "https://${azurerm_container_app.example_service.ingress[0].fqdn}"
}

output "app_ip" {
  value = join(",", azurerm_container_app.example_service.outbound_ip_addresses)
}
