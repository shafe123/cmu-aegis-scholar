# Kubernetes Deployment for AEGIS Scholar

This directory contains Helm charts and Kubernetes manifests for deploying the AEGIS Scholar research discovery system to any Kubernetes cluster.

## Architecture

The application consists of:
- **aegis-scholar-api**: REST API for research discovery
- **vector-db**: Vector similarity search service using Milvus
- **graph-db**: Graph database API service using Neo4j
- **milvus**: Standalone Milvus vector database
- **neo4j**: Neo4j graph database

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

### 5. Deploy to Development
```bash
# Install the chart
helm install aegis-scholar . \
  -f values-dev.yaml \
  -n aegis-dev \
  --set global.imageRegistry=<your-registry>

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
│       └── graph-db/              # Graph DB service chart
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
