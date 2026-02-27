# Vector DB Infrastructure

This Terraform module provisions the Azure infrastructure for the vector-db service, which provides a FastAPI interface for Milvus vector search operations.

## Resources Created

- **Resource Group**: `aegis_scholar_dev` (default)
- **Log Analytics Workspace**: For container app logging and monitoring
- **Container App Environment**: Shared environment for container apps
- **User Assigned Identity**: For pulling images from Azure Container Registry
- **Container App**: The vector-db service running on port 8002

## Configuration

### Environment Variables

The container app is configured with the following environment variables:

- `MILVUS_HOST`: Hostname of the Milvus service (default: "milvus-standalone")
- `MILVUS_PORT`: Port of the Milvus service (default: 19530)
- `DEFAULT_COLLECTION`: Default collection name (default: "aegis_vectors")
- `EMBEDDING_MODEL_NAME`: Sentence transformer model for embeddings (default: "sentence-transformers/all-MiniLM-L6-v2")

### Health Probes

Both liveness and readiness probes are configured to check the `/health` endpoint:
- **Initial Delay**: 60 seconds (allows time for embedding model download)
- **Interval**: 30 seconds
- **Timeout**: 5 seconds

### Resource Allocation

- **CPU**: 0.25 cores
- **Memory**: 0.5Gi

## Important Considerations

### Milvus Connection

The vector-db service requires a connection to a Milvus instance. In the current configuration:

- **Local Development**: Uses `milvus-standalone` from docker-compose (not accessible from Azure)
- **Production**: You'll need to configure `milvus_host` to point to:
  - An Azure Container Instance running Milvus
  - A Kubernetes-hosted Milvus cluster
  - An externally accessible Milvus service
  - Zilliz Cloud (managed Milvus offering)

### Module Variables

Override these variables when calling the module:

```terraform
module "vector_db" {
  source      = "./vector-db"
  environment = var.environment
  acr_base    = azurerm_container_registry.aegis_scholar_acr.name
  acr_id      = azurerm_container_registry.aegis_scholar_acr.id
  
  # Optional overrides
  milvus_host = "your-milvus-instance.example.com"
  milvus_port = 19530
}
```

## Outputs

- `app_url`: The FQDN of the deployed container app (HTTPS)
- `app_ip`: Outbound IP addresses of the container app

## Usage

1. Build and push the vector-db Docker image to ACR:
   ```bash
   docker build -t <acr-name>.azurecr.io/vector-db:latest ./services/vector-db
   docker push <acr-name>.azurecr.io/vector-db:latest
   ```

2. Initialize and apply Terraform:
   ```bash
   cd infra
   terraform init
   terraform plan
   terraform apply
   ```

3. Access the service at the URL from `vector_db_url` output

## Next Steps

To fully deploy this service to production, you should:

1. **Set up Milvus infrastructure** in Azure (Container Instance, AKS, or managed service)
2. **Update `milvus_host` variable** to point to your Milvus instance
3. **Configure networking** if Milvus is in a private network (VNet integration)
4. **Consider scaling** by adjusting CPU/memory or enabling auto-scaling
5. **Set up monitoring** using the Log Analytics workspace
