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

## Deployment Options

### Option 1: Kubernetes Deployment (Recommended)

Deploy to any Kubernetes cluster (local, cloud, or on-premises).

#### Prerequisites

1. **Kubernetes Cluster**: Running cluster with kubectl access
2. **Helm**: Helm 3.x installed
3. **Terraform**: v1.5.0 or later
4. **kubeconfig**: Valid kubeconfig file at `~/.kube/config`

#### Setup Steps

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
   ```bash
   export TF_VAR_neo4j_password="your-secure-password"
   export TF_VAR_registry_username="your-username"
   export TF_VAR_registry_password="your-password"
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

   Load your DTIC files into the PVC, then deploy the rest.

   **App phase** — installs the full application stack and loader jobs:
   ```bash
   terraform apply -var="deployment_phase=app"
   ```

   Or do a one-shot deployment:
   ```bash
   terraform apply -var="deployment_phase=all"
   ```

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

### Destroy Kubernetes Resources
```bash
terraform destroy
```

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
