# Integration Test Suite Map

**Total Tests:** 27 integration tests across 5 test files  
**Test Framework:** pytest with testcontainers for Docker-based integration testing  
**Scope:** All tests use session-scoped containers to minimize startup overhead

---

## Test Organization

### 📊 Graph Database Tests (6 tests)
**File:** `test_graph_neo4j.py`  
**Purpose:** Service-layer integration tests for Graph DB API ↔ Neo4j  
**Containers:** Neo4j + Graph DB service  
**Pattern:** HTTP API calls to graph-db service, validates Neo4j storage

| Test | Validates |
|------|-----------|
| `test_graph_db_service_is_healthy` | Health check reports Neo4j connected |
| `test_upsert_author_via_api` | POST /authors creates Author node |
| `test_upsert_work_via_api` | POST /works creates Work node |
| `test_link_author_work_via_api` | POST /relationships/authored creates AUTHORED relationship |
| `test_collaborator_discovery_via_api` | GET /authors/{id}/collaborators returns co-authors |
| `test_viz_network_via_api` | GET /viz/author-network/{id} returns graph structure |

---

### 🔍 Vector Database Tests (5 tests)
**File:** `test_vector_milvus.py`  
**Purpose:** Service-layer integration tests for Vector DB API ↔ Milvus  
**Containers:** Milvus + Vector DB service  
**Pattern:** HTTP API calls to vector-db service, validates Milvus storage

| Test | Validates |
|------|-----------|
| `test_vector_db_service_is_healthy` | Health check reports Milvus connected |
| `test_default_collection_created` | GET /collections shows default collection exists |
| `test_create_author_embedding_via_api` | POST /authors/embedding creates embeddings from works |
| `test_text_search_returns_results` | POST /search/text finds authors via semantic search |
| `test_models_endpoint` | GET /models returns available embedding models |

---

### 👤 Identity Service Tests (3 tests)
**File:** `test_identity_ldap.py`  
**Purpose:** Service-layer integration tests for Identity Service ↔ OpenLDAP  
**Containers:** OpenLDAP + Identity service  
**Pattern:** HTTP API calls to identity service, validates LDAP queries

| Test | Validates |
|------|-----------|
| `test_identity_service_is_healthy` | Health check reports LDAP connected |
| `test_lookup_returns_empty_for_unknown_name` | GET /lookup handles unknown names gracefully |
| `test_stats_endpoint` | GET /stats returns LDAP population metrics |

---

### 🌐 Main API → Graph DB Integration (4 tests)
**File:** `test_main_api_graph.py`  
**Purpose:** End-to-end tests for Main API ↔ Graph DB communication  
**Containers:** Neo4j + Graph DB service + Main API  
**Pattern:** Async HTTP calls to main API, validates container-to-container communication  
**Test Data:** Uses `ensure_test_data` fixture with DTIC subset

| Test | Validates |
|------|-----------|
| `test_author_details_integration` | GET /search/authors/{id} fetches author metadata from Graph DB |
| `test_viz_endpoint_integration` | GET /viz/author-network/{id} returns D3-compatible graph structure |
| `test_viz_expansion_logic` | Graph expansion logic works across depth levels |
| `test_graph_error_handling` | 404/503 error handling for non-existent authors |

---

### 🔎 Main API → Vector DB Integration (8 tests)
**File:** `test_main_api_vector.py`  
**Purpose:** End-to-end tests for Main API ↔ Vector DB communication  
**Containers:** Milvus + Vector DB service + Main API  
**Pattern:** Async HTTP calls to main API, validates semantic search integration

| Test | Validates |
|------|-----------|
| `test_health_check_reports_vector_db_status` | Main API /health reports vector DB dependency status |
| `test_author_search_integration` | GET /search/authors performs semantic search via vector DB |
| `test_author_search_with_pagination` | Pagination (limit/offset) parameters work correctly |
| `test_author_search_with_sorting` | Sort by relevance_score or citation_count works |
| `test_author_search_empty_query` | 422 validation error for missing query parameter |
| `test_author_search_respects_limits` | Min/max limit validation enforced |
| `test_vector_db_connectivity_error_handling` | 503 error when vector DB unavailable |
| `test_relevance_score_calculation` | Relevance scores properly calculated and included |

---

### 🔐 Main API → Identity Service Integration (1 test)
**File:** `test_main_api_identity.py`  
**Purpose:** End-to-end tests for Main API ↔ Identity Service communication  
**Containers:** OpenLDAP + Identity service + Main API  
**Pattern:** Async HTTP calls to main API, validates identity lookup flow

| Test | Validates |
|------|-----------|
| `test_full_identity_lookup_flow` | Complete identity lookup workflow via main API |

---

## Test Infrastructure

### Shared Fixtures (conftest.py)

**Container Fixtures (session-scoped):**
- `docker_network` - Shared network for inter-container communication
- `neo4j_container` - Neo4j database container
- `graph_db_container` - Graph DB service (builds from services/graph-db)
- `identity_container` - Identity service + OpenLDAP (builds from services/identity)
- `vector_db_container` - Vector DB service + Milvus (builds from services/vector-db)
- `aegis_scholar_api_container` - Main API (builds from services/aegis_scholar_api)

**URL Fixtures:**
- `graph_db_url` - Graph DB service URL
- `identity_api_url` - Identity service URL
- `vector_db_url` - Vector DB service URL
- `main_api_url` - Main API URL

**Data Fixtures:**
- `ensure_test_data` - Loads DTIC test subset (50 authors, topics, works) into Neo4j
- `sample_integration_data` - Sample authors, works, organizations for testing
- `sample_authors` - Extracts authors from integration data
- `sample_works` - Extracts works from integration data

**Configuration:**
- Neo4j: Port 7687 (bolt), credentials via env vars
- LDAP: Port 1389, configurable via env vars (LDAP_PORT, LDAP_BASE_DN, LDAP_ADMIN_PASSWORD)
- All services use Docker BuildKit with GitHub Actions cache support

---

## Test Execution

**Run all tests:**
```bash
poetry run pytest -v
```

**Run specific test file:**
```bash
poetry run pytest test_main_api_vector.py -v
```

**Run with coverage:**
```bash
poetry run pytest --cov=. --cov-report=term-missing
```

**Test markers:**
- `@pytest.mark.integration` - Integration test (requires Docker)
- `@pytest.mark.requires_docker` - Explicitly requires Docker
- `@pytest.mark.asyncio` - Async test

---

## Test Patterns

### Service-Level Tests (test_*_*.py)
- Test individual microservices against their backing stores
- Validate API contracts and data persistence
- Use httpx for synchronous HTTP calls
- Session-scoped containers for performance

### Main API Integration Tests (test_main_api_*.py)
- Test end-to-end flows through main API
- Validate container-to-container communication
- Use AsyncClient for async HTTP calls
- Test realistic user-facing scenarios
- Validate error handling and edge cases

---

## Coverage Summary

| Component | Unit Tests | Service Integration | API Integration |
|-----------|-----------|-------------------|-----------------|
| Graph DB | ❌ | ✅ (6 tests) | ✅ (4 tests) |
| Vector DB | ❌ | ✅ (5 tests) | ✅ (8 tests) |
| Identity | ❌ | ✅ (3 tests) | ✅ (1 test) |
| Main API | ❌ | N/A | ✅ (13 tests) |

**Next Steps:**
- Add unit tests for service business logic
- Add more identity integration tests (user authentication, authorization)
- Add tests for works and topics endpoints
- Add performance/load testing
