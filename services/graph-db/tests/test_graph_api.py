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
    """Test the visualization logic with full schema compliance."""
    mock_record = {
        "author": {"id": "auth_1", "name": "Primary Researcher", "works_count": 5, "email": "primary@dod.mil"},
        "work": {
            "id": "work_1",
            "title": "Great Research Paper",
            "publication_date": "2024-01-01",
            "citation_count": 10,
            "abstract": "This is a test abstract.",
        },
        "coAuthor": {"id": "auth_2", "name": "Co-Author Name", "works_count": 2},
        "org": {"id": "org_1", "name": "CMU"},
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

    # Verify logic from main.py
    work_node = next(n for n in data["nodes"] if n["group"] == "work")
    assert work_node["full_title"] == "Great Research Paper"
    assert work_node["year"] == "2024"
    assert work_node["citations"] == 10


# --- Additional Ingestion Tests to reach >90% Coverage ---


def test_upsert_work_success(client, mock_neo4j_session):
    """Test successful work upsert."""
    work_data = {
        "id": "work_123",
        "title": "Machine Learning for Defense",
        "name": "ML_Defense_2024",
        "type": "journal-article",
        "year": 2024,
        "citation_count": 42,
        "sources": [],
        "abstract": "Test abstract content",
        "publication_date": "2024-01-01",
    }
    response = client.post("/works", json=work_data)

    assert response.status_code == 200
    assert response.json()["id"] == "work_123"


def test_upsert_work_minimal_payload_success(client, mock_neo4j_session):
    """Minimal DTIC work payloads should not fail validation."""
    work_data = {
        "id": "work_minimal",
        "title": "Sparse DTIC Report",
        "publication_date": "2024-01-01",
        "citation_count": 0,
        "sources": [],
    }
    response = client.post("/works", json=work_data)

    assert response.status_code == 200
    assert response.json()["id"] == "work_minimal"


def test_upsert_org_success(client, mock_neo4j_session):
    """Test successful organization upsert."""
    org_data = {
        "id": "org_cmu",
        "name": "Carnegie Mellon University",
        "type": "institution",
        "country": "US",
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
        "domain": "Technology",
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


# --- Regression tests for data type handling ---


def test_viz_author_network_work_year_as_integer(client, mock_neo4j_session):
    """Regression: work.year may be an integer; should be converted to string in response.

    See: https://github.com/shafe123/cmu-aegis-scholar/issues/XX
    Graph DB stored year as integer. FastAPI response validation expected string.
    This caused: "ResponseValidationError: Input should be a valid string, input: 2016"
    """
    from unittest.mock import MagicMock

    mock_record = MagicMock()
    mock_record.__getitem__ = MagicMock(
        side_effect=lambda key: {
            "author": {"id": "auth_1", "name": "Test Author", "works_count": 1},
            "work": {
                "id": "work_1",
                "title": "Great Research Paper",
                "publication_date": None,  # No publication_date
                "year": 2016,  # Integer year instead of string
                "citation_count": 42,
                "abstract": "Test abstract",
            },
            "coAuthor": None,
            "org": None,
        }[key]
    )
    mock_neo4j_session.run.return_value = [mock_record]

    response = client.get("/viz/author-network/auth_1")
    assert response.status_code == 200
    data = response.json()

    work_node = next(n for n in data["nodes"] if n["group"] == "work")
    # The year should be converted to string "2016", not remain as int 2016
    assert work_node["year"] == "2016"
    assert isinstance(work_node["year"], str)


def test_viz_author_network_work_year_as_string_from_publication_date(client, mock_neo4j_session):
    """Year should be extracted from publication_date when available."""
    from unittest.mock import MagicMock

    mock_record = MagicMock()
    mock_record.__getitem__ = MagicMock(
        side_effect=lambda key: {
            "author": {"id": "auth_1", "name": "Test Author", "works_count": 1},
            "work": {
                "id": "work_1",
                "title": "Great Research Paper",
                "publication_date": "2024-05-12",  # Has publication_date
                "year": 2024,  # Also has year as int
                "citation_count": 42,
                "abstract": "Test abstract",
            },
            "coAuthor": None,
            "org": None,
        }[key]
    )
    mock_neo4j_session.run.return_value = [mock_record]

    response = client.get("/viz/author-network/auth_1")
    assert response.status_code == 200
    data = response.json()

    work_node = next(n for n in data["nodes"] if n["group"] == "work")
    # Should extract year from publication_date
    assert work_node["year"] == "2024"
    assert isinstance(work_node["year"], str)


def test_viz_author_network_work_year_edge_cases(client, mock_neo4j_session):
    """Year field should handle edge cases like missing both fields."""
    from unittest.mock import MagicMock

    mock_record = MagicMock()
    mock_record.__getitem__ = MagicMock(
        side_effect=lambda key: {
            "author": {"id": "auth_1", "name": "Test Author", "works_count": 1},
            "work": {
                "id": "work_1",
                "title": "Unknown Date Paper",
                "publication_date": None,  # No publication_date
                "year": None,  # No year
                "citation_count": 42,
                "abstract": "Test abstract",
            },
            "coAuthor": None,
            "org": None,
        }[key]
    )
    mock_neo4j_session.run.return_value = [mock_record]

    response = client.get("/viz/author-network/auth_1")
    assert response.status_code == 200
    data = response.json()

    work_node = next(n for n in data["nodes"] if n["group"] == "work")
    # Should default to "N/A" when both are missing
    assert work_node["year"] == "N/A"
    assert isinstance(work_node["year"], str)
