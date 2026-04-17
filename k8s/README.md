# Kubernetes Deployment for AEGIS Scholar

This directory contains Helm charts and Kubernetes manifests for deploying the AEGIS Scholar research discovery system to any Kubernetes cluster.

## Architecture

The application consists of:
- **aegis-scholar-api**: REST API for research discovery
- **vector-db**: Vector similarity search service using Milvus
- **graph-db**: Graph database API service using Neo4j
- **milvus**: Standalone Milvus vector database
- **neo4j**: Neo4j graph database
- **docker-registry**: Local container registry (dev environment only)

## Prerequisites

1. **Kubernetes Cluster**: Any Kubernetes cluster (v1.24+)
   - Local: minikube, kind, k3s, Docker Desktop
   - Cloud: AKS, EKS, GKE
   - On-premises: kubeadm, k3s

2. **kubectl**: Kubernetes CLI tool
   ```bash
   kubectl version --client
   ```

3. **Helm**: Helm 3.x
   ```bash
   helm version
   ```

4. **Traefik Ingress Controller** (recommended):
   ```bash
   helm repo add traefik https://traefik.github.io/charts
   helm install traefik traefik/traefik -n traefik-system --create-namespace
   ```

## Quick Start

### 1. Create Namespace
```bash
kubectl apply -f namespaces.yaml
```

### 2. Create Secrets
```bash
# Copy the example file
cp secrets.example.yaml secrets.yaml

# Edit with your actual credentials
# IMPORTANT: Do not commit secrets.yaml to version control!
nano secrets.yaml

# Apply secrets
kubectl apply -f secrets.yaml -n aegis-dev
```

### 3. Add Helm Repositories
```bash
# Milvus Helm chart
helm repo add milvus https://zilliztech.github.io/milvus-helm

# Neo4j Helm chart
helm repo add neo4j https://neo4j.github.io/helm-charts

# Update repositories
helm repo update
```

### 4. Build Dependencies
```bash
cd charts/aegis-scholar
helm dependency build
```

> **Note:** The development environment (`values-dev.yaml`) includes a Docker Registry for local image management. To use it, first deploy just the registry (see [Using the Built-in Docker Registry](#using-the-built-in-docker-registry)), then build and push your images, then deploy the full application.

### 5. Deploy to Development
```bash
# Install the chart
# For local development, see "Local Development with Docker Desktop" section below
# For cloud deployment, set imageRegistry to your container registry:
helm install aegis-scholar . \
  -f values-dev.yaml \
  -n aegis-dev \
  --set global.imageRegistry=myregistry.azurecr.io

# Check status
kubectl get pods -n aegis-dev
```

### 6. Access the Services
```bash
# Port forward (local development)
kubectl port-forward -n aegis-dev svc/aegis-scholar-aegis-scholar-api 8000:8000
kubectl port-forward -n aegis-dev svc/aegis-scholar-vector-db 8002:8002
kubectl port-forward -n aegis-dev svc/aegis-scholar-graph-db 8003:8003

# Via Ingress (if configured)
curl http://aegis-dev.local/api/health
```

## Local Development with Docker Desktop

### Prerequisites for Local Development

1. **Install Docker Desktop** and enable Kubernetes:
   - Open Docker Desktop → Settings → Kubernetes
   - Check "Enable Kubernetes"
   - Click "Apply & Restart"
   - Wait 2-3 minutes for Kubernetes to start

2. **Verify Kubernetes is running:**
   ```powershell
   kubectl cluster-info
   # Should show: Kubernetes control plane is running at https://kubernetes.docker.internal:6443
   ```

3. **System Requirements:**
   - 8GB+ RAM available for containers
   - 10GB+ disk space for images and volumes

### Step 1: Build Local Images

Build all service images with the `:local` tag:

```powershell
# Navigate to repository root
cd C:\Users\Ethan Shafer\Homework\CMU\cmu-aegis-scholar

# Build API service
docker build -t aegis-scholar-api:local ./services/aegis-scholar-api

# Build Vector DB service
docker build -t vector-db:local ./services/vector-db

# Build Graph DB service
docker build -t graph-db:local ./services/graph-db

# Verify images were created
docker images | Select-String "aegis-scholar|vector-db|graph-db"
```

> **Note:** Docker Desktop automatically makes locally built images available to the Kubernetes cluster.

### Step 2: Install Traefik Ingress Controller

```powershell
# Add Traefik Helm repository
helm repo add traefik https://traefik.github.io/charts
helm repo update

# Install Traefik
helm install traefik traefik/traefik `
  -n traefik-system `
  --create-namespace `
  --set ports.web.port=80

# Verify installation
kubectl get pods -n traefik-system
```

### Step 3: Create Namespace and Secrets

```powershell
# Create namespace
kubectl apply -f namespaces.yaml

# Copy and edit secrets
cp secrets.example.yaml secrets.yaml
notepad secrets.yaml  # Edit with your credentials

# Apply secrets
kubectl apply -f secrets.yaml -n aegis-dev
```

### Step 4: Prepare Helm Dependencies

```powershell
cd k8s/charts/aegis-scholar

# Add required repositories
helm repo add milvus https://zilliztech.github.io/milvus-helm
helm repo add neo4j https://neo4j.github.io/helm-charts
helm repo update

# Build dependencies (downloads Milvus and Neo4j charts)
helm dependency build
```

### Step 5: Deploy with Local Images

```powershell
# Deploy using local images (no registry)
helm install aegis-scholar . `
  -f values-dev.yaml `
  -n aegis-dev `
  --set global.imageRegistry="" `
  --set aegis-scholar-api.image.repository=aegis-scholar-api `
  --set aegis-scholar-api.image.tag=local `
  --set aegis-scholar-api.image.pullPolicy=IfNotPresent `
  --set vector-db.image.repository=vector-db `
  --set vector-db.image.tag=local `
  --set vector-db.image.pullPolicy=IfNotPresent `
  --set graph-db.image.repository=graph-db `
  --set graph-db.image.tag=local `
  --set graph-db.image.pullPolicy=IfNotPresent

# Watch deployment progress
kubectl get pods -n aegis-dev --watch
# Press Ctrl+C when all pods are Running
```

> **Alternative:** Use the built-in Docker Registry for a more production-like workflow. See the [Using the Built-in Docker Registry](#using-the-built-in-docker-registry) section below.

### Step 6: Verify Deployment

```powershell
# Check pod status
kubectl get pods -n aegis-dev

# Check services
kubectl get svc -n aegis-dev

# View API logs
kubectl logs -n aegis-dev -l app.kubernetes.io/name=aegis-scholar-api --tail=50
```

Expected pods:
- `aegis-scholar-aegis-scholar-api-xxx` (2 replicas)
- `aegis-scholar-vector-db-xxx`
- `aegis-scholar-graph-db-xxx`
- `aegis-scholar-milvus-xxx` + etcd, seaweedfs
- `aegis-scholar-neo4j-xxx`

> **Note:** Milvus may take 5-10 minutes to fully start due to initialization.

### Step 7: Access Services Locally

**Option A: Port Forwarding (Recommended)**

```powershell
# API Service
kubectl port-forward -n aegis-dev svc/aegis-scholar-aegis-scholar-api 8000:8000

# Vector DB (in another terminal)
kubectl port-forward -n aegis-dev svc/aegis-scholar-vector-db 8002:8002

# Graph DB (in another terminal)
kubectl port-forward -n aegis-dev svc/aegis-scholar-graph-db 8003:8003

# Neo4j Browser (optional, in another terminal)
kubectl port-forward -n aegis-dev svc/aegis-scholar-neo4j 7474:7474
```

Access endpoints:
- API: http://localhost:8000/health
- Vector DB: http://localhost:8002/health
- Graph DB: http://localhost:8003/health
- Neo4j Browser: http://localhost:7474

**Option B: Via Ingress**

```powershell
# Port forward to Traefik
kubectl port-forward -n traefik-system svc/traefik 8080:80

# Add to hosts file (run PowerShell as Administrator)
Add-Content -Path C:\Windows\System32\drivers\etc\hosts -Value "127.0.0.1 aegis.local"
```

Access via ingress:
- http://aegis.local:8080/api/health
- http://aegis.local:8080/vector/health
- http://aegis.local:8080/graph/health

### Testing and Validation

**Quick health check from inside the cluster:**

```powershell
kubectl run -it --rm debug --image=curlimages/curl -n aegis-dev --restart=Never -- sh -c '
  echo "Testing API..."
  curl -s http://aegis-scholar-aegis-scholar-api:8000/health
  echo -e "\n\nTesting Vector DB..."
  curl -s http://aegis-scholar-vector-db:8002/health
  echo -e "\n\nTesting Graph DB..."
  curl -s http://aegis-scholar-graph-db:8003/health
'
```

**Test Milvus connectivity:**

```powershell
$POD = kubectl get pod -n aegis-dev -l app.kubernetes.io/name=vector-db -o jsonpath='{.items[0].metadata.name}'
kubectl exec -it -n aegis-dev $POD -- python -c "from pymilvus import connections; connections.connect('default', host='aegis-scholar-milvus', port='19530'); print('Milvus connected!')"
```

**Test Neo4j connectivity:**

```powershell
$POD = kubectl get pod -n aegis-dev -l app.kubernetes.io/name=graph-db -o jsonpath='{.items[0].metadata.name}'
kubectl exec -it -n aegis-dev $POD -- python -c "from neo4j import GraphDatabase; driver = GraphDatabase.driver('bolt://aegis-scholar-neo4j:7687', auth=('neo4j', 'your-password')); driver.verify_connectivity(); print('Neo4j connected!')"
```

### Updating After Code Changes

```powershell
# 1. Rebuild the changed service image
docker build -t aegis-scholar-api:local ./services/aegis-scholar-api

# 2. Restart the deployment to pick up the new image
kubectl rollout restart deployment aegis-scholar-aegis-scholar-api -n aegis-dev

# 3. Watch the rollout
kubectl rollout status deployment aegis-scholar-aegis-scholar-api -n aegis-dev

# View logs of new pods
kubectl logs -n aegis-dev -l app.kubernetes.io/name=aegis-scholar-api -f
```

### Local Troubleshooting

**ImagePullBackOff with local images:**
```powershell
# Verify image exists locally
docker images | Select-String "aegis-scholar-api:local"

# Check pod description for pull policy
kubectl describe pod <pod-name> -n aegis-dev | Select-String "pull"

# Ensure pullPolicy is set to IfNotPresent in your Helm values
```

**Docker Desktop resource constraints:**
```powershell
# Check Docker Desktop settings
# Settings → Resources → increase Memory to 8GB+

# Check node resources
kubectl describe node docker-desktop

# View resource usage
kubectl top nodes
kubectl top pods -n aegis-dev
```

**Milvus startup issues:**
```powershell
# Milvus requires significant resources and time
kubectl get pods -n aegis-dev | Select-String milvus

# Check Milvus logs
kubectl logs -n aegis-dev -l app.kubernetes.io/name=milvus --tail=100

# Verify etcd and storage pods are running
kubectl get pods -n aegis-dev
```

**Neo4j authentication issues:**
```powershell
# Verify secret is correct
kubectl get secret neo4j-auth -n aegis-dev -o jsonpath='{.data.NEO4J_AUTH_PASSWORD}' | ForEach-Object { [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_)) }

# Check Neo4j logs
kubectl logs -n aegis-dev -l app.kubernetes.io/name=neo4j --tail=50
```

### Cleaning Up Local Environment

```powershell
# Uninstall Helm release
helm uninstall aegis-scholar -n aegis-dev

# Delete persistent volumes (this deletes all data!)
kubectl delete pvc -n aegis-dev --all

# Delete namespace
kubectl delete namespace aegis-dev

# Optional: Reset Kubernetes cluster completely
# Docker Desktop → Settings → Kubernetes → Reset Kubernetes Cluster
```

## Using the Built-in Docker Registry

The development environment includes a Docker Registry that runs inside your Kubernetes cluster. This simplifies the workflow by allowing you to push images once and reuse them across deployments.

### Step 1: Deploy Only the Registry

First, deploy just the registry component:

```powershell
cd k8s/charts/aegis-scholar

# Deploy only the docker-registry (disable other services)
helm install aegis-scholar . `
  -f values-dev.yaml `
  -n aegis-dev `
  --set aegis-scholar-api.enabled=false `
  --set vector-db.enabled=false `
  --set graph-db.enabled=false `
  --set milvus.enabled=false

# Wait for registry to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=docker-registry -n aegis-dev --timeout=2m

# Verify registry is running
kubectl get pods -n aegis-dev | Select-String docker-registry
```

The registry is:
- Accessible at `localhost:5000` (LoadBalancer)
- Configured with persistent storage (10GB by default)
- Only enabled in the dev environment

### Step 2: Configure Docker for Insecure Registry

Since this is a local HTTP registry (not HTTPS), configure Docker Desktop:

```powershell
# Open Docker Desktop → Settings → Docker Engine
# Add to the JSON configuration:
{
  "insecure-registries": ["localhost:5000"]
}

# Click "Apply & Restart"
```

### Step 3: Build and Push Images to Registry

```powershell
# Build your images
docker build -t localhost:5000/aegis-scholar-api:latest ./services/aegis-scholar-api
docker build -t localhost:5000/vector-db:latest ./services/vector-db
docker build -t localhost:5000/graph-db:latest ./services/graph-db

# Push to the cluster registry
docker push localhost:5000/aegis-scholar-api:latest
docker push localhost:5000/vector-db:latest
docker push localhost:5000/graph-db:latest
```

### Step 4: Deploy Application Services Using Registry Images

```powershell
# Now upgrade to enable all services with registry images
helm upgrade aegis-scholar . `
  -f values-dev.yaml `
  -n aegis-dev `
  --set aegis-scholar-api.enabled=true `
  --set vector-db.enabled=true `
  --set graph-db.enabled=true `
  --set milvus.enabled=true `
  --set global.imageRegistry="localhost:5000" `
  --set aegis-scholar-api.image.repository=aegis-scholar-api `
  --set aegis-scholar-api.image.tag=latest `
  --set vector-db.image.repository=vector-db `
  --set vector-db.image.tag=latest `
  --set graph-db.image.repository=graph-db `
  --set graph-db.image.tag=latest

# Watch deployment
kubectl get pods -n aegis-dev --watch
```

### Step 5: Update After Code Changes

```powershell
# Rebuild and push
docker build -t localhost:5000/aegis-scholar-api:latest ./services/aegis-scholar-api
docker push localhost:5000/aegis-scholar-api:latest

# Restart to pull new image
kubectl rollout restart deployment aegis-scholar-aegis-scholar-api -n aegis-dev
```

### Registry Management

**List images in registry:**
```powershell
# Get catalog
curl http://localhost:5000/v2/_catalog

# Get tags for a specific image
curl http://localhost:5000/v2/aegis-scholar-api/tags/list
```

**Access registry UI (optional):**
```powershell
# Deploy a registry UI
kubectl run registry-ui --image=joxit/docker-registry-ui:latest `
  -n aegis-dev `
  --env="REGISTRY_URL=http://aegis-scholar-docker-registry:5000" `
  --port=80

kubectl port-forward -n aegis-dev pod/registry-ui 8080:80
# Open http://localhost:8080 in browser
```

**Clear registry storage:**
```powershell
# Delete and recreate the PVC
kubectl delete pvc aegis-scholar-docker-registry -n aegis-dev
kubectl rollout restart deployment aegis-scholar-docker-registry -n aegis-dev
```

### Comparison: Direct Images vs Registry

**Direct local images (`:local` tag):**
- ✅ No push step required
- ✅ Faster for quick iterations
- ❌ Manual rebuild before each deploy
- ❌ Doesn't simulate production workflow

**Cluster registry (`localhost:5000`):**
- ✅ Simulates production registry workflow
- ✅ Images persist across pod restarts
- ✅ Easier rollouts (just restart deployment)
- ✅ Can version images with tags
- ❌ Requires push step
- ❌ Slightly more setup

Choose based on your workflow preference. For rapid development, use local images. For testing deployment workflows, use the registry.

## Environment-Specific Deployments

### Development
```bash
helm install aegis-scholar ./charts/aegis-scholar \
  -f charts/aegis-scholar/values-dev.yaml \
  -n aegis-dev
```

### Production
```bash
helm install aegis-scholar ./charts/aegis-scholar \
  -f charts/aegis-scholar/values-prod.yaml \
  -n aegis-prod \
  --set global.imageRegistry=myregistry.azurecr.io
```

## Configuration

### Global Settings
Override global settings in your values file:
```yaml
global:
  imageRegistry: "myregistry.azurecr.io"
  imagePullSecrets:
    - name: registry-credentials
  storageClass: "fast-ssd"
```

### Service-Specific Settings
Each service can be configured independently:
```yaml
aegis-scholar-api:
  enabled: true
  replicaCount: 3
  resources:
    limits:
      cpu: 1000m
      memory: 1Gi
```

### Ingress Configuration
Configure Traefik ingress:
```yaml
ingress:
  enabled: true
  className: traefik
  hosts:
    - host: api.aegis-scholar.com
      paths:
        - path: /api
          service: aegis-scholar-api
          port: 8000
```

## Updating Deployments

### Upgrade Release
```bash
helm upgrade aegis-scholar ./charts/aegis-scholar \
  -f charts/aegis-scholar/values-dev.yaml \
  -n aegis-dev
```

### Update Image Tags
```bash
helm upgrade aegis-scholar ./charts/aegis-scholar \
  -n aegis-dev \
  --set aegis-scholar-api.image.tag=v1.2.0 \
  --set vector-db.image.tag=v1.2.0 \
  --set graph-db.image.tag=v1.2.0
```

### Rollback
```bash
helm rollback aegis-scholar -n aegis-dev
```

## Monitoring and Debugging

### View Logs
```bash
# API logs
kubectl logs -n aegis-dev -l app.kubernetes.io/name=aegis-scholar-api -f

# Vector DB logs
kubectl logs -n aegis-dev -l app.kubernetes.io/name=vector-db -f

# Graph DB logs
kubectl logs -n aegis-dev -l app.kubernetes.io/name=graph-db -f
```

### Check Pod Status
```bash
kubectl get pods -n aegis-dev
kubectl describe pod <pod-name> -n aegis-dev
```

### Execute Commands in Pods
```bash
kubectl exec -it <pod-name> -n aegis-dev -- /bin/bash
```

## Uninstalling

### Remove Release
```bash
helm uninstall aegis-scholar -n aegis-dev
```

### Clean Up Resources
```bash
# Delete PVCs (persistent data)
kubectl delete pvc -n aegis-dev --all

# Delete namespace
kubectl delete namespace aegis-dev
```

## Troubleshooting

### Pods Not Starting
```bash
# Check events
kubectl get events -n aegis-dev --sort-by='.lastTimestamp'

# Check pod details
kubectl describe pod <pod-name> -n aegis-dev
```

### Image Pull Errors
- Verify `imagePullSecrets` are configured
- Check registry credentials in secrets
- Ensure images exist in the registry

### Service Connection Issues
- Verify services are running: `kubectl get svc -n aegis-dev`
- Check service endpoints: `kubectl get endpoints -n aegis-dev`
- Test connectivity: `kubectl run -it --rm debug --image=busybox -n aegis-dev -- sh`

### Milvus Connection Issues
- Check Milvus pod status: `kubectl get pods -n aegis-dev -l app.kubernetes.io/name=milvus`
- Verify environment variables in vector-db deployment
- Check logs: `kubectl logs -n aegis-dev -l app.kubernetes.io/name=milvus`

## Production Considerations

1. **High Availability**: Use multiple replicas and pod disruption budgets
2. **Resource Limits**: Set appropriate CPU/memory limits and requests
3. **Persistent Storage**: Use reliable storage classes (e.g., SSD-backed)
4. **Secrets Management**: Consider using external secret managers (Vault, Azure Key Vault)
5. **Monitoring**: Deploy Prometheus and Grafana for observability
6. **Backup**: Implement backup strategies for Milvus and Neo4j data
7. **TLS/SSL**: Configure HTTPS with cert-manager and Let's Encrypt
8. **Network Policies**: Implement network policies for security

## Directory Structure

```
k8s/
├── charts/
│   └── aegis-scholar/             # Umbrella chart
│       ├── Chart.yaml
│       ├── values.yaml            # Default values
│       ├── values-dev.yaml        # Development overrides
│       ├── values-prod.yaml       # Production overrides
│       ├── aegis-scholar-api/     # API service chart
│       ├── vector-db/             # Vector DB service chart
│       ├── graph-db/              # Graph DB service chart
│       └── docker-registry/       # Local registry chart (dev only)
├── namespaces.yaml                # Namespace definitions
├── secrets.example.yaml           # Secret templates
├── traefik-ingress.yaml           # Ingress configuration
└── README.md                      # This file
```

## Additional Resources

- [Helm Documentation](https://helm.sh/docs/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Traefik Documentation](https://doc.traefik.io/traefik/)
- [Milvus Documentation](https://milvus.io/docs/)
- [Neo4j Documentation](https://neo4j.com/docs/)
- [Docker Registry Documentation](https://docs.docker.com/registry/)
