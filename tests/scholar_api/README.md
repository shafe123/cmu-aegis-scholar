Aegis Scholar API
A high-performance research discovery platform that integrates Neo4j graph data with FastAPI to provide deep author analytics and network visualizations.

🚀 Quick Start
1. Environment Configuration
Create a .env file in the root directory. Ensure your Neo4j credentials match the Docker configuration.

Bash
# Database Credentials
NEO4J_PASSWORD=neo4j_password

# Service URLs
GRAPH_DB_URL=http://graph-db:8003
VECTOR_DB_URL=http://vector-db:8002

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
2. Launching the Stack
Use Docker Compose to build and start all microservices, including the Graph DB, Vector DB, and Neo4j.

Bash
docker compose up -d --build
🛠 Development & Quality Control
We maintain high code quality standards using a three-tier validation system.

1. Linting & Formatting
We use Ruff for lightning-fast formatting and Pylint for deep logic analysis.

Bash
# Format code
poetry run ruff check . --fix

# Lint logic (Aim for 9.0+ score)
poetry run pylint scholar_api/
2. Integration Testing
Tests are run against a live Dockerized Neo4j instance. Our tests cover author details, network visualization logic, and error handling.

Bash
# Run all integration tests
poetry run pytest scholar_api/test_main_graph.py -v
3. Coverage Reporting
We track code execution to ensure the most critical logic paths are verified.

Bash
# Generate terminal coverage report
poetry run pytest --cov=scholar_api scholar_api/test_main_graph.py --cov-report=term-missing
🛰 API Endpoints
Author Analytics
GET /authors/{author_id}: Returns detailed metadata for a specific author, including H-index and organizational affiliations.

Visualization
GET /viz/author-network/{author_id}: Returns a graph-ready JSON structure of nodes and edges representing an author's collaboration network.

Logic: Supports expansion flows where depth-traversal can be increased to explore secondary connections.

⚠️ Troubleshooting
Auth Errors:
If you see neo4j.exceptions.AuthError, verify that the NEO4J_PASSWORD in your .env matches the password used in scholar_api/conftest.py.

Port Conflicts:
If the stack fails to start due to "Address already in use," clear port 8080 (SeaweedFS) or 7687 (Neo4j Bolt):

Bash
sudo fuser -k 8080/tcp
Missing Data:
If an author exists in Neo4j but returns a 404, ensure the Graph DB service has been rebuilt to include the latest Cypher mapping logic:

Bash
docker compose up -d --build dev-graph-db