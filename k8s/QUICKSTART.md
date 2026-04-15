# AEGIS Scholar Kubernetes Deployment - Quick Start Guide

This guide walks you through deploying AEGIS Scholar to a Kubernetes cluster in under 15 minutes.

## Prerequisites Checklist

- [ ] Kubernetes cluster (1.24+) running and accessible
- [ ] kubectl installed and configured
- [ ] Helm 3.x installed
- [ ] Container images available in a registry (or built locally)
- [ ] 10GB+ available storage in your cluster

## Step-by-Step Deployment

### 1. Verify Cluster Access (2 minutes)

```bash
# Check cluster connection
kubectl cluster-info

# Check available storage classes
kubectl get storageclass

# Check available resources
kubectl top nodes  # Requires metrics-server
```

### 2. Install Traefik Ingress Controller (3 minutes)

```bash
# Add Traefik Helm repository
helm repo add traefik https://traefik.github.io/charts
helm repo update

# Install Traefik
helm install traefik traefik/traefik \
  -n traefik-system \
  --create-namespace \
  --set ports.web.port=80 \
  --set ports.websecure.port=443

# Verify installation
kubectl get pods -n traefik-system
```

### 3. Create Namespace (1 minute)

```bash
cd k8s
kubectl apply -f namespaces.yaml

# Verify
kubectl get namespaces | grep aegis
```

### 4. Configure Secrets (2 minutes)

```bash
# Copy example file
cp secrets.example.yaml secrets.yaml

# Edit with your credentials
# IMPORTANT: Change all passwords!
nano secrets.yaml  # or use your preferred editor

# Apply secrets
kubectl apply -f secrets.yaml -n aegis-dev

# Verify (should show 3 secrets)
kubectl get secrets -n aegis-dev
```

### 5. Build Helm Dependencies (2 minutes)

```bash
cd charts/aegis-scholar

# Add required Helm repositories
helm repo add milvus https://zilliztech.github.io/milvus-helm
helm repo add neo4j https://neo4j.github.io/helm-charts
helm repo update

# Build dependencies (downloads Milvus and Neo4j charts)
helm dependency build

# Verify Chart.lock and charts/ directory are created
ls -la
```

### 6. Deploy Application (5 minutes)

```bash
# Deploy to development environment
helm install aegis-scholar . \
  -f values-dev.yaml \
  -n aegis-dev \
  --set global.imageRegistry=<your-registry> \
  --timeout 10m

# Watch deployment progress
kubectl get pods -n aegis-dev --watch

# Wait for all pods to be Running (press Ctrl+C to stop watching)
```

Expected pods:
- aegis-scholar-aegis-scholar-api-xxx (2 replicas)
- aegis-scholar-vector-db-xxx
- aegis-scholar-graph-db-xxx
- aegis-scholar-milvus-xxx
- aegis-scholar-neo4j-xxx (and supporting pods)

### 7. Verify Deployment (2 minutes)

```bash
# Check pod status
kubectl get pods -n aegis-dev

# Check services
kubectl get svc -n aegis-dev

# Check ingress
kubectl get ingress -n aegis-dev

# View logs
kubectl logs -n aegis-dev -l app.kubernetes.io/name=aegis-scholar-api --tail=50
```

### 8. Access Services (1 minute)

**Option A: Port Forwarding (Local Development)**

```bash
# API Service
kubectl port-forward -n aegis-dev svc/aegis-scholar-aegis-scholar-api 8000:8000

# Vector DB Service
kubectl port-forward -n aegis-dev svc/aegis-scholar-vector-db 8002:8002

# Graph DB Service
kubectl port-forward -n aegis-dev svc/aegis-scholar-graph-db 8003:8003

# Neo4j Browser (optional)
kubectl port-forward -n aegis-dev svc/aegis-scholar-neo4j 7474:7474

# Access at:
# - http://localhost:8000/health (API)
# - http://localhost:8002/health (Vector DB)
# - http://localhost:8003/health (Graph DB)
# - http://localhost:7474 (Neo4j Browser)
```

**Option B: Ingress (Production)**

```bash
# Get ingress IP/hostname
kubectl get ingress -n aegis-dev

# Add to /etc/hosts (Linux/Mac) or C:\Windows\System32\drivers\etc\hosts (Windows)
<INGRESS-IP> aegis-dev.local

# Access at:
# - http://aegis-dev.local/api/health
# - http://aegis-dev.local/vector/health
# - http://aegis-dev.local/graph/health
```

## Quick Health Check

```bash
# Test all services
kubectl run -it --rm debug --image=curlimages/curl -n aegis-dev --restart=Never -- sh -c '
  echo "Testing API..."
  curl -s http://aegis-scholar-aegis-scholar-api:8000/health
  echo -e "\n\nTesting Vector DB..."
  curl -s http://aegis-scholar-vector-db:8002/health
  echo -e "\n\nTesting Graph DB..."
  curl -s http://aegis-scholar-graph-db:8003/health
'
```

## Troubleshooting Common Issues

### Pods Stuck in Pending

```bash
# Check events
kubectl get events -n aegis-dev --sort-by='.lastTimestamp' | tail -20

# Common causes:
# - Insufficient resources
# - Storage provisioning issues
# - Image pull failures
```

### Image Pull Errors

```bash
# Check image pull secrets
kubectl get secrets -n aegis-dev registry-credentials -o yaml

# Verify images exist in registry
docker pull <your-registry>/aegis-scholar-api:latest
```

### Milvus Not Starting

```bash
# Check Milvus logs
kubectl logs -n aegis-dev -l app.kubernetes.io/name=milvus --tail=100

# Common causes:
# - Insufficient memory (needs 2GB+)
# - Storage issues
# - etcd connection problems
```

### Neo4j Authentication Failures

```bash
# Check Neo4j secret
kubectl get secret neo4j-auth -n aegis-dev -o yaml

# Verify password is set correctly
kubectl get secret neo4j-auth -n aegis-dev -o jsonpath='{.data.NEO4J_AUTH_PASSWORD}' | base64 -d
```

## Updating the Deployment

```bash
# Update with new image tags
helm upgrade aegis-scholar . \
  -f values-dev.yaml \
  -n aegis-dev \
  --set aegis-scholar-api.image.tag=v1.2.0 \
  --set vector-db.image.tag=v1.2.0 \
  --set graph-db.image.tag=v1.2.0

# View release history
helm history aegis-scholar -n aegis-dev

# Rollback if needed
helm rollback aegis-scholar -n aegis-dev
```

## Cleaning Up

```bash
# Uninstall release
helm uninstall aegis-scholar -n aegis-dev

# Delete PVCs (persistent data)
kubectl delete pvc -n aegis-dev --all

# Delete namespace
kubectl delete namespace aegis-dev
```

## Next Steps

1. **Production Deployment**: Use `values-prod.yaml` with appropriate resource limits
2. **Monitoring**: Install Prometheus and Grafana for observability
3. **Backup**: Set up backup strategies for Milvus and Neo4j data
4. **TLS/SSL**: Configure HTTPS using cert-manager
5. **CI/CD**: Implement automated deployments with GitHub Actions

## Getting Help

- Check pod logs: `kubectl logs -n aegis-dev <pod-name>`
- Describe resources: `kubectl describe pod <pod-name> -n aegis-dev`
- View events: `kubectl get events -n aegis-dev`
- Helm status: `helm status aegis-scholar -n aegis-dev`

For more detailed information, see:
- [k8s/README.md](README.md)
- [infra/README.md](../infra/README.md)
