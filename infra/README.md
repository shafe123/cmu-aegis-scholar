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

4. **Enable Kubernetes Module**
   Edit `main.tf` and uncomment the `k8s_deployment` module block.

5. **Plan Deployment**
   ```bash
   terraform plan
   ```

6. **Apply Configuration**
   ```bash
   terraform apply
   ```

#### Connecting to Different Kubernetes Clusters

**Local Clusters (minikube, kind, Docker Desktop)**
```hcl
# terraform.tfvars
kubeconfig_path = "~/.kube/config"
```

**Azure AKS**
```bash
# Get credentials
az aks get-credentials --resource-group <rg> --name <cluster-name>

# Terraform will use default kubeconfig
kubeconfig_path = "~/.kube/config"
```

**AWS EKS**
```bash
# Get credentials
aws eks update-kubeconfig --name <cluster-name> --region <region>

# Terraform will use default kubeconfig
kubeconfig_path = "~/.kube/config"
```

**GCP GKE**
```bash
# Get credentials
gcloud container clusters get-credentials <cluster-name> --zone <zone>

# Terraform will use default kubeconfig
kubeconfig_path = "~/.kube/config"
```

**Custom/Self-Hosted Cluster**
```hcl
# terraform.tfvars
kubeconfig_path = "/path/to/your/kubeconfig"
```

Or configure inline credentials in `main.tf`:
```hcl
provider "kubernetes" {
  host                   = var.kubernetes_host
  token                  = var.kubernetes_token
  cluster_ca_certificate = base64decode(var.kubernetes_ca_cert)
}
```

### Option 2: Azure Container Apps (Legacy)

Deploy to Azure Container Apps using the existing modules.

#### Prerequisites

1. **Azure Subscription**: Active Azure subscription
2. **Azure CLI**: Logged in with `az login`
3. **Terraform**: v1.5.0 or later

#### Setup Steps

1. **Initialize Terraform**
   ```bash
   cd infra
   terraform init
   ```

2. **Configure Variables**
   ```bash
   # Edit variables in terraform.tfvars or use defaults
   environment = "dev"
   location = "eastus"
   ```

3. **Apply Configuration**
   ```bash
   terraform apply
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

## Managing State

### Remote State (Azure Backend)

The configuration uses Azure Storage for remote state:

```hcl
backend "azurerm" {
  resource_group_name  = "aegis_scholar_essential"
  storage_account_name = "aegisscholarterraform"
  container_name       = "tfstate"
  key                  = "terraform.tfstate"
}
```

### Multiple Environments

Use workspaces for multiple environments:

```bash
# Create and switch to dev workspace
terraform workspace new dev
terraform workspace select dev

# Apply dev configuration
terraform apply -var="environment=dev"

# Create and switch to prod workspace
terraform workspace new prod
terraform workspace select prod

# Apply prod configuration
terraform apply -var="environment=prod"
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
