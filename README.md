# cmu-aegis-scholar

## Getting Started

### Prerequisites
- Docker and Docker Compose installed on your system
- VS Code with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### Running the Dev Container

1. **Open the project in VS Code**
   ```bash
   code /path/to/cmu-aegis-scholar
   ```

2. **Reopen in Dev Container**
   - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS)
   - Select "Dev Containers: Reopen in Container"
   - Wait for the container to build and start

3. **Start Developing**
   - The dev container is now running with all dependencies pre-installed
   - You can run services, tests, and development commands directly in the integrated terminal

### Common Development Tasks

**Run tests:**
```bash
cd services/example-service
pytest
```

**Start a service:**
```bash
cd services/example-service
python -m app.main
```

**Install Python dependencies:**
```bash
pip install -e .
```

### Project Structure
- `services/` - Microservices and backend applications
- `libs/` - Shared libraries and packages
- `infra/` - Infrastructure and deployment configurations (Terraform)
- `k8s/` - Kubernetes manifests
- `dev/` - Development utilities and Docker Compose configuration