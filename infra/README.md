# Infrastructure as Code (Terraform)

This directory contains Terraform configurations for deploying AEGIS Scholar infrastructure. The configuration supports both Azure-specific resources (Azure Container Apps, ACR) and generic Kubernetes deployments.

## Directory Structure

```
infra/
├── main.tf                    # Main configuration with provider setup
├── variables.tf               # Variable definitions
├── output.tf                  # Output definitions
├── terraform.tfvars.example   # Example variable values
├── example-service/           # Azure Container Apps example
├── vector-db/                 # Azure Container Apps vector-db module
├── k8s-deployment/            # Kubernetes deployment module
│   ├── main.tf
│   ├── variables.tf
│   └── output.tf
└── README.md                  # This file
```

## Kubernetes Deployment

Deploy to any Kubernetes cluster (local, cloud, or on-premises).

### Prerequisites

1. **Kubernetes Cluster**: Running cluster with kubectl access
2. **Helm**: Helm 3.x installed
3. **Terraform**: v1.5.0 or later
4. **kubeconfig**: Valid kubeconfig file at `~/.kube/config`

### Setup Steps

1. **Initialize Terraform**
   ```bash
   cd infra
   terraform init
   ```

2. **Configure Variables**
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   nano terraform.tfvars  # Edit with your values
   ```

3. **Set Secrets via Environment Variables**
   Use the same terminal session that you will run Terraform from.

   ```powershell
   $env:TF_VAR_neo4j_password="your-secure-password"
   $env:TF_VAR_registry_username="your-username"
   $env:TF_VAR_registry_password="your-password"
   ```

4. **Apply by stage (recommended for local development)**

   **Bootstrap phase** — namespace, Traefik, local registry wiring:
   ```bash
   terraform apply -var="deployment_phase=bootstrap"
   ```

   **Data phase** — creates the shared DTIC PVC:
   ```bash
   terraform apply -var="deployment_phase=data"
   ```

   **Load DTIC files into the PVC**:
   ```powershell
   $helperPodYaml = @(
     'apiVersion: v1'
     'kind: Pod'
     'metadata:'
     '  name: data-loader-helper'
     '  namespace: aegis-dev'
     'spec:'
     '  containers:'
     '  - name: helper'
     '    image: busybox'
     '    command: ["sh", "-c", "sleep 3600"]'
     '    volumeMounts:'
     '    - name: dtic-data'
     '      mountPath: /data'
     '  volumes:'
     '  - name: dtic-data'
     '    persistentVolumeClaim:'
     '      claimName: dtic-data'
   ) -join "`n"

   $helperPodYaml | kubectl apply -f -
   kubectl wait --for=condition=ready pod/data-loader-helper -n aegis-dev --timeout=2m
   kubectl cp ../data/dtic_compressed data-loader-helper:/data/ -n aegis-dev -c helper
   kubectl exec -n aegis-dev data-loader-helper -- ls -lh /data/dtic_compressed/
   kubectl delete pod data-loader-helper -n aegis-dev
   ```

   **App phase** — builds images and installs the full application stack:
   
   ```bash
   terraform apply -var="deployment_phase=app"
   ```

   **Note:** Images are automatically built and pushed to the local registry during this phase. To skip automatic builds (if you've built images manually), set:
   ```bash
   terraform apply -var="deployment_phase=app" -var="build_images=false"
   ```

   **⏱️ Note:** The app phase can take 10-20 minutes to complete because:
   - Container images must be built from source (if `build_images=true`)
   - Built images must be pushed to the local registry
   - Helm charts must be downloaded and dependencies resolved (Milvus, Neo4j)
   - Large database images need to be pulled (Neo4j ~800MB, Milvus components ~2GB total)
   - Neo4j and Milvus require time to initialize their databases
   - Loader jobs must process and ingest all DTIC data files
   - Health checks must pass before Terraform considers the deployment complete

   You can monitor progress in another terminal with:
   ```powershell
   kubectl get pods -n aegis-dev --watch
   ```

### Validation

After deployment completes, verify the application is running correctly:

1. **Check Namespaces**
   ```powershell
   kubectl get namespaces
   # Should see: aegis-dev and traefik-system
   ```

2. **Check All Pods**
   ```powershell
   # Overview of all pods in aegis-dev
   kubectl get pods -n aegis-dev
   
   # All pods should show Running or Completed (for jobs)
   ```

3. **Check Loader Jobs**
   ```powershell
   # Verify loader jobs completed successfully
   kubectl get jobs -n aegis-dev
   
   # Check logs if needed
   kubectl logs job/graph-loader -n aegis-dev
   kubectl logs job/vector-loader -n aegis-dev
   ```

4. **Check Services**
   ```powershell
   kubectl get svc -n aegis-dev
   kubectl get ingress -n aegis-dev
   ```

5. **Test API Health**
   ```powershell
   # Port forward to API
   kubectl port-forward -n aegis-dev svc/aegis-scholar-api 8000:8000
   
   # In another terminal
   curl http://localhost:8000/health
   ```

6. **Access Frontend**
   ```powershell
   # Port forward to frontend
   kubectl port-forward -n aegis-dev svc/frontend 3000:3000
   
   # Open browser to http://localhost:3000
   ```

**Common Issues:**
- **ImagePullBackOff**: Images not built/pushed to registry - verify with `curl http://localhost:5000/v2/_catalog`
- **CrashLoopBackOff**: Application crashes on startup - check logs with `kubectl logs`
- **Jobs not completing**: Data loading failures - verify DTIC data was copied correctly
- **Pending pods**: Resource constraints or PVC mounting issues

For detailed troubleshooting, see the [Troubleshooting](#troubleshooting) section below.

## Configuration Variables

### Required Variables

| Variable          | Description            | Example                       |
| ----------------- | ---------------------- | ----------------------------- |
| `environment`     | Deployment environment | `dev`, `staging`, `prod`      |
| `kubeconfig_path` | Path to kubeconfig     | `~/.kube/config`              |
| `helm_chart_path` | Path to Helm chart     | `../k8s/charts/aegis-scholar` |

### Optional Variables

| Variable               | Description            | Default               |
| ---------------------- | ---------------------- | --------------------- |
| `kubernetes_namespace` | K8s namespace          | `aegis-{environment}` |
| `helm_release_name`    | Helm release name      | `aegis-scholar`       |
| `image_registry`       | Container registry URL | ``                    |
| `image_tag`            | Container image tag    | `latest`              |

### Sensitive Variables

Set these via environment variables (recommended) or in `terraform.tfvars` (not recommended for production):

```bash
export TF_VAR_neo4j_password="secure-password"
export TF_VAR_registry_username="username"
export TF_VAR_registry_password="password"
```

## Outputs

After successful deployment, Terraform provides useful outputs:

```bash
# View all outputs
terraform output

# View specific output
terraform output namespace
```

Available outputs:
- `namespace`: Kubernetes namespace
- `helm_release_name`: Helm release name
- `helm_release_status`: Deployment status
- `helm_release_version`: Deployed version

## Updating Deployments

### Update Image Tags
```bash
terraform apply -var="image_tag=v1.2.3"
```

### Update Configuration
1. Edit `terraform.tfvars` or chart values
2. Run `terraform plan` to preview changes
3. Run `terraform apply` to apply changes

### Update Helm Chart
Helm chart changes are automatically detected and applied.

## Destroying Resources

### Recommended staged teardown

For local development, tear down in reverse order:

```bash
terraform apply -var="deployment_phase=data"
terraform apply -var="deployment_phase=bootstrap"
terraform destroy
```

This removes the application layer before the shared infrastructure and reduces the chance of stuck service cleanup during destroy.

### Destroy Kubernetes Resources
```bash
terraform destroy
```

**Note:** Terraform now properly manages both the `aegis-dev` and `traefik-system` namespaces, so they will be cleaned up automatically during destroy.

### Destroy Specific Module
```bash
terraform destroy -target=module.k8s_deployment
```

## Troubleshooting

### Provider Authentication Issues

**Kubernetes Provider**
```bash
# Verify kubectl access
kubectl cluster-info

# Verify kubeconfig
cat ~/.kube/config
```

**Azure Provider**
```bash
# Verify Azure login
az account show

# Re-authenticate if needed
az login
```

### State Locking Issues
```bash
# Force unlock (use with caution)
terraform force-unlock <lock-id>
```

### Module Not Found
```bash
# Re-initialize
terraform init -upgrade
```

### Helm Release Failures

Check Kubernetes pods:
```bash
kubectl get pods -n aegis-dev
kubectl logs <pod-name> -n aegis-dev
```

View Helm release:
```bash
helm list -n aegis-dev
helm status aegis-scholar -n aegis-dev
```

## Security Best Practices

1. **Never commit secrets** to version control
2. **Use environment variables** for sensitive values
3. **Consider secret management systems**: Azure Key Vault, HashiCorp Vault, AWS Secrets Manager
4. **Enable backend encryption** for state files
5. **Use RBAC** for Kubernetes access control
6. **Rotate credentials** regularly

## Additional Resources

- [Terraform Documentation](https://www.terraform.io/docs)
- [Kubernetes Provider](https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs)
- [Helm Provider](https://registry.terraform.io/providers/hashicorp/helm/latest/docs)
- [Azure Provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs)
