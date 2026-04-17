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

> **Note:** The development environment (`values-dev.yaml`) includes a Docker Registry for local image management. The registry requires a DaemonSet configuration to work correctly on Docker Desktop. See [Using the Built-in Docker Registry](#using-the-built-in-docker-registry) for complete setup instructions.

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

## Loading DTIC Data

The deployment includes automatic data loader jobs that run on install/upgrade via Helm hooks. However, these jobs require the DTIC compressed data files to be available in a PersistentVolumeClaim (PVC) named `dtic-data`.

### Understanding the Data Loading Process

When you install or upgrade the Helm chart:
1. A PVC named `dtic-data` is created automatically
2. Two Kubernetes Jobs are triggered via Helm hooks:
   - `aegis-scholar-graph-db-loader`: Loads authors, organizations, topics, and works into Neo4j
   - `aegis-scholar-vector-db-loader`: Loads work embeddings into Milvus
3. Both jobs read from `/data/dtic_compressed` in the PVC
4. If no data files are found, the jobs complete successfully but don't load anything
5. Jobs are automatically deleted before each upgrade (via `before-hook-creation` policy)

### One-Time Setup: Populate the PVC with Data

**Prerequisites:**
- DTIC data files available in your workspace at `data/dtic_compressed/`
- Expected files: `dtic_authors_*.jsonl.gz`, `dtic_orgs_*.jsonl.gz`, `dtic_topics_*.jsonl.gz`, `dtic_works_*.jsonl.gz`

**Step 1: Deploy a helper pod to access the PVC**

```powershell
# Create a simple pod that mounts the dtic-data PVC
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

**Step 2: Copy your DTIC data into the PVC**

```powershell
# Copy the entire dtic_compressed directory into the PVC
kubectl cp data/dtic_compressed data-loader-helper:/data/ -n aegis-dev -c helper

# Verify the data was copied
kubectl exec -n aegis-dev data-loader-helper -- ls -lh /data/dtic_compressed/
```

You should see output like:
```
-rw-r--r-- 1 root root  12M Apr 17 18:30 dtic_authors_001.jsonl.gz
-rw-r--r-- 1 root root 123M Apr 17 18:30 dtic_works_001.jsonl.gz
...
```

**Step 3: Clean up the helper pod**

```powershell
kubectl delete pod data-loader-helper -n aegis-dev
```

**Step 4: Trigger the loader jobs**

The loader jobs run automatically on `helm upgrade`:

```powershell
cd k8s/charts/aegis-scholar

# Trigger a Helm upgrade to re-run the loader jobs
helm upgrade aegis-scholar . -f values-dev.yaml -n aegis-dev

# Watch the loader jobs
kubectl get jobs -n aegis-dev -w
```

You should see:
```
NAME                             COMPLETIONS   DURATION   AGE
aegis-scholar-graph-db-loader    1/1           45s        1m
aegis-scholar-vector-db-loader   1/1           2m30s      2m
```

**Step 5: Verify data was loaded**

```powershell
# Check graph-db loader logs
kubectl logs -n aegis-dev -l app.kubernetes.io/component=loader,app.kubernetes.io/name=graph-db --tail=50

# Check vector-db loader logs
kubectl logs -n aegis-dev -l app.kubernetes.io/component=loader,app.kubernetes.io/name=vector-db --tail=50

# Query Neo4j to verify data
kubectl exec -n aegis-dev deployment/aegis-scholar-graph-db -- \
  python -c "from neo4j import GraphDatabase; d = GraphDatabase.driver('bolt://aegis-scholar-neo4j:7687', auth=('neo4j', 'your-password')); print(d.execute_query('MATCH (n) RETURN count(n) as count'))"

# Query Milvus via Vector DB API
kubectl exec -n aegis-dev deployment/aegis-scholar-vector-db -- \
  curl -s http://localhost:8002/collections/aegis_vectors
```

### Updating Data

If you need to update the DTIC data files:

1. Delete existing data from PVC (optional - will be overwritten):
   ```powershell
   kubectl run --rm -it data-cleanup --image=busybox -n aegis-dev --restart=Never -- sh -c 'rm -rf /data/dtic_compressed/*' --overrides='{"spec":{"volumes":[{"name":"dtic-data","persistentVolumeClaim":{"claimName":"dtic-data"}}],"containers":[{"name":"data-cleanup","image":"busybox","command":["sh","-c","rm -rf /data/dtic_compressed/*"],"volumeMounts":[{"name":"dtic-data","mountPath":"/data"}]}]}}'
   ```

2. Follow Steps 1-4 above to copy new data and trigger reload

### Troubleshooting Data Loading

**Jobs complete but no data loaded:**
```powershell
# Check if PVC has data
kubectl run --rm -it check-pvc --image=busybox -n aegis-dev --restart=Never -- ls -lh /data/dtic_compressed --overrides='{"spec":{"volumes":[{"name":"dtic-data","persistentVolumeClaim":{"claimName":"dtic-data"}}],"containers":[{"name":"check-pvc","image":"busybox","command":["ls","-lh","/data/dtic_compressed"],"volumeMounts":[{"name":"dtic-data","mountPath":"/data"}]}]}}'

# If empty, repeat the kubectl cp step
```

**kubectl cp fails with "no such file or directory":**
```powershell
# Ensure you're in the repository root
cd C:\Users\<YourUsername>\Homework\CMU\cmu-aegis-scholar

# Verify data directory exists locally
Test-Path data/dtic_compressed
Get-ChildItem data/dtic_compressed -File | Select-Object -First 5
```

**Jobs fail with errors:**
```powershell
# View job pod logs
kubectl get pods -n aegis-dev -l app.kubernetes.io/component=loader

# Check specific job logs
kubectl logs -n aegis-dev aegis-scholar-graph-db-loader-xxxxx
kubectl logs -n aegis-dev aegis-scholar-vector-db-loader-xxxxx
```

**Need to re-run loader jobs manually:**
```powershell
# Delete old jobs
kubectl delete job aegis-scholar-graph-db-loader aegis-scholar-vector-db-loader -n aegis-dev

# Run helm upgrade to trigger hooks again
helm upgrade aegis-scholar . -f values-dev.yaml -n aegis-dev
```

## Using the Built-in Docker Registry

The development environment includes a Docker Registry that runs inside your Kubernetes cluster. This simplifies the workflow by allowing you to push images once and reuse them across deployments.

> **Docker Desktop Note:** This setup uses a specialized configuration to work around Docker Desktop's built-in registry-mirror, which intercepts image pulls and causes conflicts with in-cluster registries.

### Step 1: Deploy the Registry and Containerd Configuration

The registry requires both the registry pod and a DaemonSet that configures containerd to bypass Docker Desktop's registry-mirror:

```powershell
cd k8s/charts/aegis-scholar

# Build Helm dependencies
helm dependency build

# Deploy the registry and services (registry is enabled by default in values-dev.yaml)
helm install aegis-scholar . `
  -f values-dev.yaml `
  -n aegis-dev

# Apply the registry configuration DaemonSet
kubectl apply -f ..\registry-config-daemonset.yaml

# Wait for registry to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=docker-registry -n aegis-dev --timeout=2m

# Verify registry is running
kubectl get pods -n aegis-dev | Select-String docker-registry
```

**What's happening:**
- The registry runs with `hostNetwork: true` to bind to the node's `localhost:5000`
- The DaemonSet creates a containerd configuration at `/etc/containerd/certs.d/aegis-scholar-docker-registry.aegis-dev.svc.cluster.local/hosts.toml`
- This configuration tells containerd to pull from `localhost:5000` when pods request images from the FQDN `aegis-scholar-docker-registry.aegis-dev.svc.cluster.local`
- This bypasses Docker Desktop's registry-mirror which would otherwise intercept the image pulls

The registry is:
- Accessible inside cluster at `aegis-scholar-docker-registry.aegis-dev.svc.cluster.local:5000`
- Accessible from Windows host via port-forward
- Configured with persistent storage (10GB by default)
- Only enabled in the dev environment

### Step 2: Set Up Port Forwarding to Access Registry from Host

Since the registry uses cluster DNS, you need port-forward to push images from your Windows host:

```powershell
# Port forward in a separate terminal window (keep this running)
kubectl port-forward -n aegis-dev svc/aegis-scholar-docker-registry 5000:5000
```

> **Important:** Keep this port-forward running while building and pushing images.

### Step 3: Build and Push Images to Registry

```powershell
# Build your images with localhost:5000 tag (for pushing via port-forward)
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

> **Note:** Images are pushed using `localhost:5000` (via port-forward), but Kubernetes pods pull them using the FQDN `aegis-scholar-docker-registry.aegis-dev.svc.cluster.local`. The containerd configuration maps between these.

### Step 4: Verify Pods Can Pull Images

The images are automatically pulled by the deployments. Check pod status:

```powershell
# Check all pods
kubectl get pods -n aegis-dev

# If pods are in ImagePullBackOff, check the describe output
kubectl describe pod <pod-name> -n aegis-dev

# Verify successful pulls - should see "Successfully pulled image" events
kubectl get events -n aegis-dev --sort-by='.lastTimestamp' | Select-String "Successfully pulled"
```

Expected pod states:
- `aegis-scholar-aegis-scholar-api-xxx`: Running (or CrashLoopBackOff if app config issue)
- `aegis-scholar-vector-db-xxx`: Running
- `aegis-scholar-graph-db-xxx`: Running
- `aegis-scholar-docker-registry-xxx`: Running

### Step 5: Update After Code Changes

```powershell
# Rebuild and push (ensure port-forward is still running)
docker build -t localhost:5000/aegis-scholar-api:latest ./services/aegis-scholar-api
docker push localhost:5000/aegis-scholar-api:latest

# Restart deployment to pull new image
kubectl rollout restart deployment aegis-scholar-aegis-scholar-api -n aegis-dev

# Watch the rollout
kubectl rollout status deployment aegis-scholar-aegis-scholar-api -n aegis-dev

# View logs of new pods
kubectl logs -n aegis-dev -l app.kubernetes.io/name=aegis-scholar-api -f
```

### Registry Management

**List images in registry:**
```powershell
# Ensure port-forward is running, then:
curl http://localhost:5000/v2/_catalog

# Get tags for a specific image
curl http://localhost:5000/v2/aegis-scholar-api/tags/list
```

**Test registry from inside cluster:**
```powershell
kubectl run curl-test --image=curlimages/curl:latest --rm -it --restart=Never -n aegis-dev -- \
  curl http://aegis-scholar-docker-registry.aegis-dev.svc.cluster.local:5000/v2/_catalog
```

**View registry logs:**
```powershell
kubectl logs -n aegis-dev -l app.kubernetes.io/name=docker-registry -f
```

**Clear registry storage:**
```powershell
# Delete and recreate the PVC (warning: deletes all images!)
helm uninstall aegis-scholar -n aegis-dev
kubectl delete pvc aegis-scholar-docker-registry -n aegis-dev

# Reinstall
helm install aegis-scholar . -f values-dev.yaml -n aegis-dev
kubectl apply -f ..\registry-config-daemonset.yaml
```

### Troubleshooting Registry Issues

**ImagePullBackOff with "registry-mirror" error:**
```powershell
# Verify the DaemonSet is running
kubectl get daemonset registry-config -n aegis-dev

# Check DaemonSet logs
kubectl logs -n aegis-dev -l name=registry-config -c configure-containerd

# Should see: "Registry configuration applied successfully"
# If not, reapply the DaemonSet
kubectl delete daemonset registry-config -n aegis-dev
kubectl apply -f ..\registry-config-daemonset.yaml
```

**Can't push images from Windows host:**
```powershell
# Verify port-forward is running
# You should see: Forwarding from 127.0.0.1:5000 -> 5000

# Test registry connectivity
curl http://localhost:5000/v2/_catalog

# If connection refused, restart port-forward:
kubectl port-forward -n aegis-dev svc/aegis-scholar-docker-registry 5000:5000
```

**Pods can't pull images (DNS resolution error):**
```powershell
# Verify registry pod is running with hostNetwork
kubectl get pod -n aegis-dev -l app.kubernetes.io/name=docker-registry -o yaml | Select-String hostNetwork
# Should show: hostNetwork: true

# Check if registry is listening on port 5000
kubectl exec -n aegis-dev deployment/aegis-scholar-docker-registry -- netstat -tlnp | Select-String 5000
```

### How It Works: Docker Desktop Registry-Mirror Workaround

**The Problem:**
Docker Desktop includes a built-in registry-mirror service that intercepts image pulls containing a port number (e.g., `registry:5000`). This causes 500 errors when trying to use an in-cluster registry.

**The Solution:**
1. **Host Network**: Registry runs with `hostNetwork: true`, binding to node's `localhost:5000`
2. **FQDN Without Port**: Image references use `aegis-scholar-docker-registry.aegis-dev.svc.cluster.local` (no port in the image name)
3. **Containerd Config**: DaemonSet creates `/etc/containerd/certs.d/<FQDN>/hosts.toml` that maps the FQDN to `localhost:5000`
4. **Default Port**: Registry uses standard port 5000, so containerd assumes port 5000 when not specified in image name

This way:
- Image names have no port → registry-mirror doesn't intercept
- Containerd knows to use `localhost:5000` for that FQDN
- Registry on `hostNetwork` is accessible at `localhost:5000` from the node

### Comparison: Direct Images vs Registry

**Direct local images (`:local` tag):**
- ✅ No push step required
- ✅ Faster for quick iterations
- ✅ No port-forward needed
- ❌ Manual rebuild before each deploy
- ❌ Doesn't simulate production workflow

**Cluster registry:**
- ✅ Simulates production registry workflow
- ✅ Images persist across pod restarts
- ✅ Easier rollouts (just restart deployment)
- ✅ Can version images with tags
- ✅ Tests registry authentication/authorization
- ❌ Requires push step
- ❌ Requires port-forward to push
- ❌ More complex setup

Choose based on your workflow preference. For rapid development, use local images. For testing deployment workflows or CI/CD simulation, use the registry.

## Data Loading Jobs

The deployment includes automatic data loading via Kubernetes Jobs that run once during installation/upgrade:

### Overview

- **graph-loader**: Loads DTIC scholarly data into Neo4j (authors, organizations, topics, works)
- **vector-loader**: Generates and loads embeddings into Milvus vector database

Both jobs run automatically as Helm hooks during `helm install` or `helm upgrade`.

### How It Works

1. **Helm Hook Execution**: Jobs run with `post-install` and `post-upgrade` hooks
2. **Service Wait**: Jobs wait for their respective services to be healthy
3. **Idempotent Loading**: Jobs check if data already exists (`SKIP_IF_LOADED=true`)
4. **Shared Data Volume**: Both jobs read from a shared `dtic-data` PersistentVolumeClaim containing compressed DTIC data
5. **Clean Up**: Jobs are automatically deleted before re-running (via `before-hook-creation` policy)
6. **TTL**: Completed jobs are cleaned up after 24 hours

### Multi-Replica Safety

Jobs run **once per deployment**, not per pod replica:
- ✅ Safe to scale `vector-db` or `graph-db` to multiple replicas
- ✅ Jobs won't duplicate work across pods
- ✅ Idempotent design prevents duplicate data loading

### Monitoring Job Status

```powershell
# Check job status
kubectl get jobs -n aegis-dev

# View loader logs
kubectl logs -n aegis-dev job/aegis-scholar-graph-db-loader
kubectl logs -n aegis-dev job/aegis-scholar-vector-db-loader

# Check if data is loaded
kubectl exec -n aegis-dev -it deployment/aegis-scholar-graph-db -- curl http://localhost:8003/stats
kubectl exec -n aegis-dev -it deployment/aegis-scholar-vector-db -- curl http://localhost:8002/collections
```

### Manual Job Control

```powershell
# Disable loaders (in values file)
helm upgrade aegis-scholar ./charts/aegis-scholar \
  -f values-dev.yaml \
  -n aegis-dev \
  --set graph-db.loader.enabled=false \
  --set vector-db.loader.enabled=false

# Manually trigger data loading (delete and reinstall)
kubectl delete job -n aegis-dev aegis-scholar-graph-db-loader
kubectl delete job -n aegis-dev aegis-scholar-vector-db-loader
helm upgrade aegis-scholar ./charts/aegis-scholar -f values-dev.yaml -n aegis-dev
```

### Preparing Data Volume

The loaders expect a `dtic-data` PersistentVolumeClaim with compressed DTIC data:

```powershell
# The PVC is created automatically by the Helm chart
# You need to populate it with data

# Option 1: Copy data from local machine
kubectl cp ./data/dtic_compressed aegis-dev/data-loader-pod:/data/dtic_compressed

# Option 2: Use an init container or Job to download/prepare data
# See data preparation documentation for details
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

### Pods Crashing on Startup

**API pod crashes with "ValueError: Unknown level":**
```powershell
# Check logs
kubectl logs -n aegis-dev -l app.kubernetes.io/name=aegis-scholar-api --tail=20

# If you see: ValueError: Unknown level: 'debug'
# Python's logging requires uppercase log levels (DEBUG, INFO, WARNING, ERROR)
# Fix in values-dev.yaml:
# Change: value: "debug"
# To: value: "DEBUG"

# Apply the fix
helm upgrade aegis-scholar . -f values-dev.yaml -n aegis-dev
kubectl rollout restart deployment aegis-scholar-aegis-scholar-api -n aegis-dev
```

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
