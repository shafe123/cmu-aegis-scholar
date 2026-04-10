from unittest.mock import MagicMock


def test_root_endpoint(client):
    """Test the base health/info endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Graph API" in response.json().get("title", "")


def test_health_check_success(client, mock_neo4j_session):
    """Verify health reports 'healthy' when Neo4j responds."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    mock_neo4j_session.run.assert_called_with("RETURN 1")


def test_health_check_failure(client, mock_neo4j_session):
    """Verify health reports 'unhealthy' when Neo4j is down."""
    mock_neo4j_session.run.side_effect = Exception("Connection Refused")
    response = client.get("/health")
    assert response.json()["status"] == "unhealthy"
    assert "Connection Refused" in response.json()["error"]


def test_get_stats_success(client, mock_neo4j_session):
    """Test /stats returns correctly formatted count."""
    mock_result = MagicMock()
    mock_result.single.return_value = {"count": 17245}
    mock_neo4j_session.run.return_value = mock_result

    response = client.get("/stats")
    assert response.status_code == 200
    assert response.json()["author_count"] == 17245


def test_get_stats_db_error(client, mock_neo4j_session):
    """Test /stats returns 500 on database failure."""
    mock_neo4j_session.run.side_effect = Exception("Query Timeout")
    response = client.get("/stats")
    assert response.status_code == 500
    assert "Graph database connection error" in response.json()["detail"]


def test_upsert_author_validation_error(client):
    """Test Pydantic validation for missing required fields."""
    response = client.post("/authors", json={"name": "No ID Provided"})
    assert response.status_code == 422  # Unprocessable Entity


def test_upsert_author_success(client, mock_neo4j_session):
    """Test successful author upsert calls Cypher correctly."""
    author_data = {"id": "author_123", "name": "Dr. Test", "h_index": 10, "works_count": 5}
    response = client.post("/authors", json=author_data)
    assert response.status_code == 200
    # Ensure MERGE query was used
    args, kwargs = mock_neo4j_session.run.call_args
    assert "MERGE (a:Author {id: $id})" in args[0]
    assert kwargs["id"] == "author_123"


def test_get_collaborators_mapping(client, mock_neo4j_session):
    """Verify Cypher records are correctly transformed to a JSON list."""
    mock_result = [{"id": "collab_1", "name": "Author A"}, {"id": "collab_2", "name": "Author B"}]
    mock_neo4j_session.run.return_value = mock_result

    response = client.get("/authors/author_original/collaborators")
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["name"] == "Author A"


def test_viz_network_logic(client, mock_neo4j_session):
    """Test the logic for flattening graph nodes and edges for frontend JS."""
    # Mock complex Neo4j response structure
    mock_record = {
        "a": {"id": "auth_1", "name": "Primary Author"},
        "w": {"id": "work_1", "title": "Great Research Paper"},
        "co": {"id": "auth_2", "name": "Co-Author"},
    }
    mock_neo4j_session.run.return_value = [mock_record]

    response = client.get("/viz/author-network/auth_1")
    assert response.status_code == 200
    data = response.json()

    # Check nodes
    ids = [n["id"] for n in data["nodes"]]
    assert "auth_1" in ids
    assert "work_1" in ids
    assert "auth_2" in ids

    # Check groups for frontend coloring
    node_types = [n["group"] for n in data["nodes"]]
    assert "author" in node_types
    assert "work" in node_types

    # Check edges (connections)
    assert len(data["edges"]) >= 2  # Primary -> Work and CoAuthor -> Work
