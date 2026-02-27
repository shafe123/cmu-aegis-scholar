output "acr_address" {
  value = azurerm_container_registry.aegis_scholar_acr.login_server
}

output "example_service_url" {
  value = module.example_serivce.app_url
}


output "example_service_ip" {
  value = module.example_serivce.app_ip
}

output "vector_db_url" {
  value = module.vector_db.app_url
}

output "vector_db_ip" {
  value = module.vector_db.app_ip
}
