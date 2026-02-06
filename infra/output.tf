output "acr_address" {
  value = azurerm_container_registry.aegis_scholar_acr.login_server
}

output "example_service_url" {
  value = module.example_serivce.app_url
}


output "example_service_ip" {
  value = module.example_serivce.app_ip
}
