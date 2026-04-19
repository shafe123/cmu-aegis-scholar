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
    """
    Test the visualization logic. 
    FIXED: Keys now match the production RETURN statement (author, work, coAuthor, org).
    """
    mock_record = {
        "author": {"id": "auth_1", "name": "Primary"},
        "work": {"id": "work_1", "title": "Paper", "year": 2024, "citation_count": 0},
        "coAuthor": {"id": "auth_2", "name": "CoAuthor"},
        "org": {"id": "org_1", "name": "CMU"}
    }
    mock_neo4j_session.run.return_value = [mock_record]
    
    response = client.get("/viz/author-network/auth_1")
    assert response.status_code == 200
    data = response.json()
    
    # Verify node extraction
    ids = [n["id"] for n in data["nodes"]]
    assert "auth_1" in ids
    assert "work_1" in ids
    assert "org_1" in ids

    # Check groups for frontend coloring
    node_types = [n["group"] for n in data["nodes"]]
    assert "author" in node_types
    assert "work" in node_types

    # Check edges (connections)
    assert len(data["edges"]) >= 2  # Primary -> Work and CoAuthor -> Work

# --- Additional Ingestion Tests to reach >90% Coverage ---

def test_upsert_work_success(client, mock_neo4j_session):
    """Test successful work upsert."""
    # FIXED: Added 'name' and 'type' to match the WorkNode schema requirements
    work_data = {
        "id": "work_123",
        "title": "Machine Learning for Defense",
        "name": "ML_Defense_2024",  # Added required field
        "type": "journal-article",   # Added required field
        "year": 2024,
        "citation_count": 42,
        "sources": [],
        "abstract": "Test abstract content",
        "publication_date": "2024-01-01"
    }
    response = client.post("/works", json=work_data)
    
    assert response.status_code == 200
    assert response.json()["id"] == "work_123"


def test_upsert_org_success(client, mock_neo4j_session):
    """Test successful organization upsert."""
    org_data = {
        "id": "org_cmu",
        "name": "Carnegie Mellon University",
        "type": "institution",
        "country": "US"
    }
    response = client.post("/orgs", json=org_data)
    assert response.status_code == 200
    assert response.json()["id"] == "org_cmu"


def test_upsert_topic_success(client, mock_neo4j_session):
    """Test successful topic upsert."""
    topic_data = {
        "id": "topic_ai",
        "name": "Artificial Intelligence",
        "field": "Computer Science",
        "domain": "Technology"
    }
    response = client.post("/topics", json=topic_data)
    assert response.status_code == 200
    assert response.json()["id"] == "topic_ai"


# --- Additional Relationship Tests ---

def test_link_author_work_success(client, mock_neo4j_session):
    """Test linking an author to a work."""
    payload = {"author_id": "author_123", "work_id": "work_123"}
    response = client.post("/relationships/authored", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "linked"


def test_link_author_org_success(client, mock_neo4j_session):
    """Test linking an author to an organization."""
    payload = {"author_id": "author_123", "org_id": "org_cmu", "role": "Researcher"}
    response = client.post("/relationships/affiliated", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "linked"


def test_link_work_topic_success(client, mock_neo4j_session):
    """Test linking a work to a topic."""
    payload = {"work_id": "work_123", "topic_id": "topic_ai", "score": 0.95}
    response = client.post("/relationships/covers", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "linked"