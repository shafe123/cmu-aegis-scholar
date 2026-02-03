# cmu-aegis-scholar

## Getting Started

### Prerequisites
- Docker and Docker Compose installed on your system
- VS Code with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### Running the Dev Container

1. Create the `dev_aegisnet` docker network
   ```bash
   docker network create dev_aegisnet
   ```

1. **Open the project in VS Code**
   ```bash
   code /path/to/cmu-aegis-scholar
   ```

1. **Reopen in Dev Container**
   - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS)
   - Select "Dev Containers: Reopen in Container"
   - Wait for the container to build and start

1. **Start Developing**
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

## Running the Example Service with Docker Compose

To start the example service using Docker Compose, run the following command from the root directory:

```sh
docker compose -f dev/docker-compose.yml up --build -d example-service
```

This will build and start the example service defined in `dev/docker-compose.yml`.