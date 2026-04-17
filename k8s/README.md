# Kubernetes Deployment for Aegis Scholar

This directory contains Helm charts and Kubernetes manifests for deploying the Aegis Scholar research discovery system to any Kubernetes cluster.

## Architecture

The application consists of:
- **aegis-scholar-api**: REST API for research discovery
- **vector-db**: Vector similarity search service using Milvus
- **graph-db**: Graph database API service using Neo4j
- **milvus**: Standalone Milvus vector database
- **neo4j**: Neo4j graph database
- **docker-registry**: Local container registry (dev environment only)
- **graph-loader**: Kubernetes Job that loads DTIC data into Neo4j
- **vector-loader**: Kubernetes Job that loads embeddings into Milvus

## Prerequisites

1. **Kubernetes Cluster**: Any Kubernetes cluster (v1.24+)
   - Local: Docker Desktop (recommended for development), minikube, kind, k3s
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

4. **Docker**: For building and pushing images
   ```bash
   docker version
   ```

5. **System Requirements** (for local development):
   - 8GB+ RAM available for containers
   - 10GB+ disk space for images and volumes

6. **DTIC Data**: Compressed DTIC data files
   - Expected location: `data/dtic_compressed/` in your workspace
   - Expected files: `dtic_authors_*.jsonl.gz`, `dtic_orgs_*.jsonl.gz`, `dtic_topics_*.jsonl.gz`, `dtic_works_*.jsonl.gz`
   - Total size: ~70MB (compressed)

## Local Development Deployment (Docker Desktop)

This guide walks through deploying Aegis Scholar on Docker Desktop using the built-in registry. This simulates a production-like workflow while remaining fully local.

### Step 1: Enable Kubernetes in Docker Desktop

1. Open Docker Desktop → Settings → Kubernetes
2. Check "Enable Kubernetes"
3. Click "Apply & Restart"
4. Wait 2-3 minutes for Kubernetes to start

**Verify Kubernetes is running:**
```powershell
kubectl cluster-info
# Should show: Kubernetes control plane is running at https://kubernetes.docker.internal:6443
```

---

### Step 2: Prepare DTIC Data Volume

**⚠️ Important:** Load your DTIC data BEFORE deploying the application. The loader jobs will read from this data during deployment.

#### 2.1 Create Namespace

#### 2.1 Create Namespace

```powershell
# Create namespace
kubectl apply -f namespaces.yaml
```

#### 2.2 Create PVC for DTIC Data

```powershell
@'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: dtic-data
  namespace: aegis-dev
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
'@ | kubectl apply -f -

# Verify PVC was created
kubectl get pvc -n aegis-dev
```

#### 2.3 Deploy Helper Pod

```powershell
@'
apiVersion: v1
kind: Pod
metadata:
  name: data-loader-helper
  namespace: aegis-dev
spec:
  containers:
  - name: helper
    image: busybox
    command: ["sh", "-c", "sleep 3600"]
    volumeMounts:
    - name: dtic-data
      mountPath: /data
  volumes:
  - name: dtic-data
    persistentVolumeClaim:
      claimName: dtic-data
'@ | kubectl apply -f -

# Wait for pod to be ready
kubectl wait --for=condition=ready pod/data-loader-helper -n aegis-dev --timeout=2m
```

#### 2.4 Copy DTIC Data to PVC

```powershell
# Copy the entire dtic_compressed directory into the PVC
kubectl cp data/dtic_compressed data-loader-helper:/data/ -n aegis-dev -c helper

# Verify the data was copied
kubectl exec -n aegis-dev data-loader-helper -- ls -lh /data/dtic_compressed/
```

You should see output like:
```
-rw-r--r-- 1 root root  12M Apr 17 18:30 dtic_authors_001.jsonl.gz
-rw-r--r-- 1 root root   5M Apr 17 18:30 dtic_orgs_001.jsonl.gz
-rw-r--r-- 1 root root  23M Apr 17 18:30 dtic_topics_001.jsonl.gz
-rw-r--r-- 1 root root  30M Apr 17 18:30 dtic_works_001.jsonl.gz
```

#### 2.5 Clean Up Helper Pod

```powershell
kubectl delete pod data-loader-helper -n aegis-dev
```

✅ **Data is ready!** Loader jobs will automatically use this data during deployment.

---

### Step 3: Create Secrets

```powershell
# Copy and edit secrets
cp secrets.example.yaml secrets.yaml
notepad secrets.yaml  # Edit with your credentials

# Apply secrets
kubectl apply -f secrets.yaml -n aegis-dev
```

**⚠️ Important:** Do not commit `secrets.yaml` to version control!

---

### Step 4: Install Traefik Ingress Controller (Optional)

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

---

### Step 5: Prepare Helm Dependencies

```powershell
cd k8s/charts/aegis-scholar

# Add required repositories
helm repo add milvus https://zilliztech.github.io/milvus-helm
helm repo add neo4j https://neo4j.github.io/helm-charts
helm repo update

# Build dependencies (downloads Milvus and Neo4j charts)
helm dependency build
```

---

### Step 6: Deploy Built-in Registry

Deploy the chart with the built-in registry enabled:

```powershell
# Deploy just the registry first
helm install aegis-scholar . `
  -f values-dev.yaml `
  -n aegis-dev `
  --set aegis-scholar-api.enabled=false `
  --set vector-db.enabled=false `
  --set graph-db.enabled=false `
  --set milvus.enabled=false

# Apply the registry configuration DaemonSet
kubectl apply -f ..\..\registry-config-daemonset.yaml

# Wait for registry to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=docker-registry -n aegis-dev --timeout=2m

# Verify registry is running
kubectl get pods -n aegis-dev | Select-String docker-registry
```

**What's happening:**
- The registry runs with `hostNetwork: true` to bind to the node's `localhost:5000`
- The DaemonSet creates a containerd configuration that allows pods to pull images from `aegis-scholar-docker-registry.aegis-dev.svc.cluster.local:5000`
- This bypasses Docker Desktop's registry-mirror which would otherwise intercept image pulls

---

### Step 7: Build and Push Images

#### 7.1 Start Port Forward (keep running in a separate terminal)

**Open a new PowerShell window** and run:

```powershell
# Port forward to the registry - KEEP THIS RUNNING
kubectl port-forward -n aegis-dev svc/aegis-scholar-docker-registry 5000:5000
```

#### 7.2 Build and Push Service Images

In your main terminal:

```powershell
# Build images with localhost:5000 tag (for pushing via port-forward)
docker build -t localhost:5000/aegis-scholar-api:latest ./services/aegis-scholar-api
docker build -t localhost:5000/vector-db:latest ./services/vector-db
docker build -t localhost:5000/graph-db:latest ./services/graph-db

# Push to the cluster registry (via port-forward)
docker push localhost:5000/aegis-scholar-api:latest
docker push localhost:5000/vector-db:latest
docker push localhost:5000/graph-db:latest

# Verify images were pushed
curl http://localhost:5000/v2/_catalog
# Should return: {"repositories":["aegis-scholar-api","graph-db","vector-db"]}
```

#### 7.3 Build and Push Loader Images

```powershell
# Build loader images
docker build -t localhost:5000/graph-loader:latest ./jobs/graph-loader
docker build -t localhost:5000/vector-loader:latest ./jobs/vector-loader

# Push to registry
docker push localhost:5000/graph-loader:latest
docker push localhost:5000/vector-loader:latest

# Verify all images
curl http://localhost:5000/v2/_catalog
# Should return: {"repositories":["aegis-scholar-api","graph-db","graph-loader","vector-db","vector-loader"]}
```

---

### Step 8: Deploy Complete Application

Now deploy all services. The loader jobs will automatically run and load data from the PVC:

```powershell
# Upgrade to enable all services
helm upgrade aegis-scholar . -f values-dev.yaml -n aegis-dev

# Watch deployment progress
kubectl get pods -n aegis-dev --watch
# Press Ctrl+C when all pods are Running
```

**Expected pods:**
- `aegis-scholar-0` (Neo4j StatefulSet)
- `aegis-scholar-aegis-scholar-api-xxx` (2 replicas)
- `aegis-scholar-vector-db-xxx`
- `aegis-scholar-graph-db-xxx`
- `aegis-scholar-milvus-standalone-xxx` + supporting services (etcd, minio)
- `aegis-scholar-docker-registry-xxx`
- `aegis-scholar-graph-db-loader-xxx` (Job - will complete and terminate)
- `aegis-scholar-vector-db-loader-xxx` (Job - will complete and terminate)

> **Note:** Neo4j and Milvus may take 5-10 minutes to fully start due to initialization.

---

### Step 9: Monitor Data Loading

The loader jobs run automatically during deployment:

```powershell
# Watch loader job status
kubectl get jobs -n aegis-dev -w

# Check graph-db loader logs
kubectl logs -n aegis-dev -l app.kubernetes.io/component=loader,app.kubernetes.io/name=graph-db -f

# Check vector-db loader logs
kubectl logs -n aegis-dev -l app.kubernetes.io/component=loader,app.kubernetes.io/name=vector-db -f
```

**Loader jobs will show:**
- **graph-db-loader**: Loading authors, organizations, topics, works into Neo4j
- **vector-db-loader**: Generating and loading embeddings into Milvus

Jobs should complete with status `1/1` (may take 5-15 minutes depending on data size).

---

### Step 10: Verify Deployment

```powershell
# Check all pods are running
kubectl get pods -n aegis-dev

# Check services
kubectl get svc -n aegis-dev

# Verify data was loaded - check Neo4j node count
kubectl exec -n aegis-dev deployment/aegis-scholar-graph-db -- `
  curl -s http://localhost:8003/stats

# Verify vector data - check Milvus collection
kubectl exec -n aegis-dev deployment/aegis-scholar-vector-db -- `
  curl -s http://localhost:8002/collections/aegis_vectors
```

---

### Step 11: Access Services

```powershell
# Port forward to Traefik
kubectl port-forward -n traefik-system svc/traefik 8080:80

# Access via ingress
curl http://localhost:8080/api/health
curl http://localhost:8080/vector/health
curl http://localhost:8080/graph/health
```

---

## Updating After Code Changes

When you modify code, rebuild and push images, then restart deployments:

```powershell
# Ensure port-forward to registry is running
kubectl port-forward -n aegis-dev svc/aegis-scholar-docker-registry 5000:5000

# Rebuild and push (example: API service)
docker build -t localhost:5000/aegis-scholar-api:latest ./services/aegis-scholar-api
docker push localhost:5000/aegis-scholar-api:latest

# Restart deployment to pull new image
kubectl rollout restart deployment aegis-scholar-aegis-scholar-api -n aegis-dev

# Watch the rollout
kubectl rollout status deployment aegis-scholar-aegis-scholar-api -n aegis-dev

# View logs of new pods
kubectl logs -n aegis-dev -l app.kubernetes.io/name=aegis-scholar-api -f
```

**For loader images:**

```powershell
# Rebuild and push
docker build -t localhost:5000/graph-loader:latest ./jobs/graph-loader
docker push localhost:5000/graph-loader:latest

# Delete old jobs and trigger re-run via Helm upgrade
kubectl delete jobs -n aegis-dev -l app.kubernetes.io/component=loader
helm upgrade aegis-scholar . -f values-dev.yaml -n aegis-dev

# Jobs will automatically re-run
kubectl get jobs -n aegis-dev -w
```

---

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
