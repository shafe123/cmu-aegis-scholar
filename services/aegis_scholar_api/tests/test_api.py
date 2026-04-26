"""
Unit tests for Aegis Scholar API.

All downstream services (vector DB, graph DB) are mocked.
No live network connections are required.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Helpers — test in isolation without HTTP overhead
# ---------------------------------------------------------------------------


def test_distance_to_relevance_perfect_match():
    """Distance of 0 should give relevance of 1.0."""
    from app.main import _distance_to_relevance

    assert _distance_to_relevance(0.0) == 1.0


def test_distance_to_relevance_typical():
    """Typical distance should give a score between 0 and 1."""
    from app.main import _distance_to_relevance

    score = _distance_to_relevance(0.5)
    assert 0 < score < 1


def test_distance_to_relevance_large():
    """Large distance should give a score close to 0."""
    from app.main import _distance_to_relevance

    score = _distance_to_relevance(999.0)
    assert score < 0.01


async def test_map_vector_results_valid():
    """Valid results should be mapped to AuthorSearchResult objects."""
    from app.main import _map_vector_results

    raw = [
        {
            "author_id": "author_1a2b3c4d-1234-5678-abcd-1234567890ab",
            "author_name": "Dr. Test",
            "num_abstracts": 10,
            "citation_count": 500,
            "distance": 0.3,
        }
    ]
    results = await _map_vector_results(raw)
    assert len(results) == 1
    assert results[0].id == "author_1a2b3c4d-1234-5678-abcd-1234567890ab"
    assert results[0].name == "Dr. Test"
    assert results[0].works_count == 10
    assert results[0].citation_count == 500
    assert 0 < results[0].relevance_score <= 1.0


def test_calculate_author_relevance_matches_wolfram_formula():
    """Formula should match the WolframAlpha equation exactly."""
    import math

    from app.main import _calculate_author_relevance

    score = _calculate_author_relevance(x=0.8, y=100, t=2.0)
    sigmoid_term = 1.0 / (1.0 + math.exp(-0.005 * (100 - 100)))
    recency_term = (-math.tanh(2.0 - 2.0) + 1.0) / 2.0
    assert score == round(((1.0 - 0.8) + sigmoid_term + recency_term) / 3.0, 4)
    assert score == 0.4


@pytest.mark.parametrize(
    ("x", "y", "t", "expected"),
    [
        # Best vector match (x=0), very high citations, oldest allowed work (t=4)
        (0.0, 0, 4.0, 0.4652),
        # Worst vector match (x=1), maximum citations, most recent possible work (t=0)
        (1.0, 10000, 0.0, 0.6607),
        # Mid-range across all three terms
        (0.5, 100, 2.0, 0.5),
    ],
)
def test_calculate_author_relevance_range_examples(x, y, t, expected):
    """Equation should behave correctly at representative input ranges.

    Expected values are precomputed from the same WolframAlpha equation.
    """
    from app.main import _calculate_author_relevance

    assert _calculate_author_relevance(x=x, y=y, t=t) == expected


async def test_map_vector_results_prefers_more_recent_work():
    """Newer most recent work should improve relevance for equal x/y."""
    from datetime import date

    from app.main import _map_vector_results
    from app.services.graph_db import graph_client

    current_year = date.today().year
    raw = [
        {
            "author_id": "author_1a2b3c4d-1234-5678-abcd-1234567890ab",
            "author_name": "Recent",
            "num_abstracts": 10,
            "citation_count": 500,
            "distance": 0.3,
        },
        {
            "author_id": "author_2b3c4d5e-2345-6789-bcde-2345678901bc",
            "author_name": "Older",
            "num_abstracts": 10,
            "citation_count": 500,
            "distance": 0.3,
        },
    ]

    async def _year_by_author(author_id: str) -> int | None:
        # "1a2b" is a substring of the "Recent" author's ID; return the current year for them
        # and current_year - 40 (4 decades ago) for the "Older" author.
        return current_year if "1a2b" in author_id else current_year - 40

    with patch.object(graph_client, "get_most_recent_work_year", side_effect=_year_by_author):
        results = await _map_vector_results(raw)
    assert results[0].name == "Recent"


async def test_map_vector_results_malformed_skipped():
    """Malformed results missing required fields should be skipped."""
    from app.main import _map_vector_results

    raw = [{"bad_field": "no_id_here"}]
    results = await _map_vector_results(raw)
    assert len(results) == 0


async def test_map_vector_results_empty():
    """Empty input should return empty list."""
    from app.main import _map_vector_results

    assert await _map_vector_results([]) == []


async def test_sort_author_results_by_citation_desc():
    """Results should be sortable by citation_count descending."""
    from app.main import _map_vector_results, _sort_author_results

    raw = [
        {
            "author_id": "author_1a2b3c4d-1234-5678-abcd-1234567890ab",
            "author_name": "Low",
            "num_abstracts": 1,
            "citation_count": 10,
            "distance": 0.1,
        },
        {
            "author_id": "author_2b3c4d5e-2345-6789-bcde-2345678901bc",
            "author_name": "High",
            "num_abstracts": 1,
            "citation_count": 9999,
            "distance": 0.5,
        },
    ]
    results = await _map_vector_results(raw)
    sorted_results = _sort_author_results(results, "citation_count", "desc")
    assert sorted_results[0].citation_count == 9999


async def test_sort_author_results_by_citation_asc():
    """Results should be sortable by citation_count ascending."""
    from app.main import _map_vector_results, _sort_author_results

    raw = [
        {
            "author_id": "author_1a2b3c4d-1234-5678-abcd-1234567890ab",
            "author_name": "Low",
            "num_abstracts": 1,
            "citation_count": 10,
            "distance": 0.1,
        },
        {
            "author_id": "author_2b3c4d5e-2345-6789-bcde-2345678901bc",
            "author_name": "High",
            "num_abstracts": 1,
            "citation_count": 9999,
            "distance": 0.5,
        },
    ]
    results = await _map_vector_results(raw)
    sorted_results = _sort_author_results(results, "citation_count", "asc")
    assert sorted_results[0].citation_count == 10


async def test_sort_author_results_invalid_field_returns_original():
    """Invalid sort field should return results unchanged."""
    from app.main import _map_vector_results, _sort_author_results

    raw = [
        {
            "author_id": "author_1a2b3c4d-1234-5678-abcd-1234567890ab",
            "author_name": "First",
            "num_abstracts": 1,
            "citation_count": 10,
            "distance": 0.1,
        },
    ]
    results = await _map_vector_results(raw)
    sorted_results = _sort_author_results(results, "nonexistent_field", "desc")
    assert sorted_results == results


async def test_sort_author_results_no_sort_field():
    """None sort field should return results unchanged."""
    from app.main import _map_vector_results, _sort_author_results

    raw = [
        {
            "author_id": "author_1a2b3c4d-1234-5678-abcd-1234567890ab",
            "author_name": "First",
            "num_abstracts": 1,
            "citation_count": 10,
            "distance": 0.1,
        },
    ]
    results = await _map_vector_results(raw)
    sorted_results = _sort_author_results(results, None, "desc")
    assert sorted_results == results


# ---------------------------------------------------------------------------
# System endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_root_endpoint(async_client):
    """Root endpoint should return API metadata."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert "endpoints" in data


@pytest.mark.asyncio
async def test_health_check_vector_db_healthy(async_client):
    """Health check should report healthy when vector DB responds."""
    with patch("app.services.vector_db.health", new_callable=AsyncMock) as mock_health:
        mock_health.return_value = {"status": "healthy"}
        response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["dependencies"]["vector_db"] == "healthy"


@pytest.mark.asyncio
async def test_health_check_vector_db_unreachable(async_client):
    """Health check should still return 200 but report vector DB as unreachable."""
    with patch("app.services.vector_db.health", new_callable=AsyncMock) as mock_health:
        mock_health.side_effect = Exception("connection refused")
        response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "unreachable" in data["dependencies"]["vector_db"]


# ---------------------------------------------------------------------------
# Search endpoints — authors (primary functionality)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_authors_success(async_client, mock_vector_db_search):
    """Successful author search should return mapped results."""
    with patch("app.services.vector_db.search_by_text", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_vector_db_search
        response = await async_client.get("/search/authors?q=machine+learning")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "machine learning"
    assert len(data["results"]) == 2
    assert data["results"][0]["name"] == "Dr. Jane Smith"


@pytest.mark.asyncio
async def test_search_authors_empty_results(async_client, mock_vector_db_empty):
    """Author search with no matches should return empty results list."""
    with patch("app.services.vector_db.search_by_text", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_vector_db_empty
        response = await async_client.get("/search/authors?q=zzznomatch")
    assert response.status_code == 200
    data = response.json()
    assert data["results"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_search_authors_with_limit(async_client, mock_vector_db_search):
    """Limit parameter should be respected."""
    with patch("app.services.vector_db.search_by_text", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_vector_db_search
        response = await async_client.get("/search/authors?q=ai&limit=1")
    assert response.status_code == 200
    assert response.json()["limit"] == 1


@pytest.mark.asyncio
async def test_search_authors_sort_by_citation(async_client, mock_vector_db_search):
    """sort_by=citation_count should re-sort results."""
    with patch("app.services.vector_db.search_by_text", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_vector_db_search
        response = await async_client.get("/search/authors?q=ai&sort_by=citation_count&order=desc")
    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["citation_count"] >= results[-1]["citation_count"]


@pytest.mark.asyncio
async def test_search_authors_connect_error(async_client):
    """ConnectError from vector DB should return 503."""
    with patch("app.services.vector_db.search_by_text", new_callable=AsyncMock) as mock_search:
        mock_search.side_effect = httpx.ConnectError("refused")
        response = await async_client.get("/search/authors?q=test")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_search_authors_upstream_error(async_client):
    """HTTP error from vector DB should return 502."""
    with patch("app.services.vector_db.search_by_text", new_callable=AsyncMock) as mock_search:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_search.side_effect = httpx.HTTPStatusError("error", request=MagicMock(), response=mock_response)
        response = await async_client.get("/search/authors?q=test")
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_search_alias_delegates_to_search_authors(async_client, mock_vector_db_search):
    """/search should behave identically to /search/authors."""
    with patch("app.services.vector_db.search_by_text", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_vector_db_search
        response = await async_client.get("/search?q=neural+networks")
    assert response.status_code == 200
    assert "results" in response.json()


# ---------------------------------------------------------------------------
# Search endpoints — orgs, topics, works (all 501 Not Implemented)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_orgs_not_implemented(async_client):
    """Org search should return 501 until graph DB is wired."""
    response = await async_client.get("/search/orgs?q=MIT")
    assert response.status_code == 501


@pytest.mark.asyncio
async def test_search_topics_not_implemented(async_client):
    """Topic search should return 501 until taxonomy is loaded."""
    response = await async_client.get("/search/topics?q=AI")
    assert response.status_code == 501


@pytest.mark.asyncio
async def test_search_works_not_implemented(async_client):
    """Work search should return 501 until metadata store is connected."""
    response = await async_client.get("/search/works?q=transformers")
    assert response.status_code == 501


# ---------------------------------------------------------------------------
# Detail endpoints — all 501 Not Implemented
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_work_by_id_not_implemented(async_client):
    response = await async_client.get("/search/works/work_abc123")
    assert response.status_code == 501


@pytest.mark.asyncio
async def test_get_author_by_id_success(async_client):
    """Successfully retrieve author from graph DB."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "author_1a2b3c4d-1234-5678-abcd-1234567890ab",
            "name": "Dr. Jane Smith",
            "h_index": 10,
            "works_count": 42,
            "organizations": [{"id": "org_1a2b3c4d-1234-5678-abcd-1234567890ab"}],
        }
        mock_instance.get.return_value = mock_response
        mock_client_class.return_value = mock_instance
        response = await async_client.get("/search/authors/author_1a2b3c4d-1234-5678-abcd-1234567890ab")
    assert response.status_code == 200
    assert response.json()["name"] == "Dr. Jane Smith"


async def test_get_author_by_id_not_found(async_client):
    """Graph DB returning 404 should bubble up as 404."""
    # Patch the specific method on the instance used in main.py
    with patch("app.main.graph_client.get_author_details", new_callable=AsyncMock) as mock_get:
        # Create a mock response that looks like a 404
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 404
        mock_resp.request = MagicMock(spec=httpx.Request)

        # Make the mock raise the error FastAPI expects to catch
        mock_get.side_effect = httpx.HTTPStatusError(message="Not Found", request=mock_resp.request, response=mock_resp)

        response = await async_client.get("/search/authors/author_1a2b3c4d-1234-5678-abcd-1234567890ab")

        assert response.status_code == 404
        assert response.json()["detail"] == "Author not found"


@pytest.mark.asyncio
async def test_get_author_by_id_graph_db_unavailable(async_client):
    """Graph DB being unreachable should return 503."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get.side_effect = httpx.ConnectError("refused")
        mock_client_class.return_value = mock_instance
        response = await async_client.get("/search/authors/author_1a2b3c4d-1234-5678-abcd-1234567890ab")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_get_org_by_id_not_implemented(async_client):
    response = await async_client.get("/search/orgs/org_abc123")
    assert response.status_code == 501


@pytest.mark.asyncio
async def test_get_topic_by_id_not_implemented(async_client):
    response = await async_client.get("/search/topics/topic_abc123")
    assert response.status_code == 501


# ---------------------------------------------------------------------------
# vector_db service — init, close, get_client
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vector_db_init_and_close():
    """init_client and close_client should create and destroy the client."""
    from app.services import vector_db

    await vector_db.init_client()
    assert vector_db._client is not None
    await vector_db.close_client()
    assert vector_db._client is None


@pytest.mark.asyncio
async def test_vector_db_get_client_raises_when_not_initialized():
    """_get_client should raise RuntimeError if client is None."""
    from app.services import vector_db

    vector_db._client = None
    with pytest.raises(RuntimeError):
        vector_db._get_client()


# ---------------------------------------------------------------------------
# graph_db service — basic client behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_db_client_get_collaborators():
    """get_collaborators should call the graph DB service."""
    from app.services.graph_db import GraphDBClient

    client = GraphDBClient()
    mock_response = MagicMock()
    mock_response.json.return_value = [{"id": "author_1a2b3c4d-1234-5678-abcd-1234567890ab", "name": "Test"}]
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await client.get_collaborators("author_1a2b3c4d-1234-5678-abcd-1234567890ab")
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_graph_db_client_get_viz_data():
    """get_viz_data should call the graph DB visualization endpoint."""
    from app.services.graph_db import GraphDBClient

    client = GraphDBClient()
    mock_response = MagicMock()
    mock_response.json.return_value = {"nodes": [], "edges": []}
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await client.get_viz_data("author_1a2b3c4d-1234-5678-abcd-1234567890ab")
    assert "nodes" in result


def test_graph_db_client_uses_configured_settings():
    """GraphDBClient should read its base URL and timeout from settings."""
    from app.config import settings
    from app.services.graph_db import GraphDBClient

    client = GraphDBClient()

    assert client.url == settings.graph_db_url
    assert client.timeout.connect == settings.graph_db_timeout
    assert client.timeout.read == settings.graph_db_timeout


# ---------------------------------------------------------------------------
# Regression tests for data type handling
# ---------------------------------------------------------------------------


async def test_map_vector_results_citation_count_as_string():
    """Regression: citation_count from vector DB may be a string; should be converted to int.

    See: https://github.com/shafe123/cmu-aegis-scholar/issues/XX
    Vector DB returned citation_count as string instead of int, causing
    "unsupported operand type(s) for -: 'int' and 'str'" when calculating relevance.
    """
    from app.main import _map_vector_results

    raw = [
        {
            "author_id": "author_1a2b3c4d-1234-5678-abcd-1234567890ab",
            "author_name": "Dr. Test String Citations",
            "num_abstracts": 10,
            "citation_count": "500",  # String instead of int
            "distance": 0.3,
        }
    ]
    results = await _map_vector_results(raw)
    assert len(results) == 1
    assert results[0].citation_count == 500
    assert isinstance(results[0].citation_count, int)
    assert 0 < results[0].relevance_score <= 1.0


async def test_map_vector_results_citation_count_as_int():
    """citation_count as integer should also work correctly."""
    from app.main import _map_vector_results

    raw = [
        {
            "author_id": "author_1a2b3c4d-1234-5678-abcd-1234567890ab",
            "author_name": "Dr. Test Int Citations",
            "num_abstracts": 10,
            "citation_count": 500,  # Integer (normal case)
            "distance": 0.3,
        }
    ]
    results = await _map_vector_results(raw)
    assert len(results) == 1
    assert results[0].citation_count == 500
    assert isinstance(results[0].citation_count, int)


async def test_map_vector_results_citation_count_edge_cases():
    """citation_count conversion should handle edge cases like "0", None, etc."""
    from app.main import _map_vector_results

    test_cases = [
        (0, 0),  # Zero int
        ("0", 0),  # Zero string
        (1000000, 1000000),  # Large int
        ("1000000", 1000000),  # Large string
    ]

    for i, (input_val, expected) in enumerate(test_cases):
        raw = [
            {
                "author_id": f"author_1a2b3c4d-1234-5678-abcd-123456789{i:03d}",
                "author_name": f"Dr. Test {input_val}",
                "num_abstracts": 1,
                "citation_count": input_val,
                "distance": 0.1,
            }
        ]
        results = await _map_vector_results(raw)
        assert len(results) == 1, f"Failed for input {input_val}"
        assert results[0].citation_count == expected, f"Expected {expected}, got {results[0].citation_count}"


def test_calculate_decades_since_most_recent_work_with_int():
    """Most recent work year as integer should work correctly."""
    from datetime import date
    from unittest.mock import patch

    from app.main import _calculate_decades_since_most_recent_work

    # Mock date.today() to return a fixed date for deterministic testing
    mock_today = date(2026, 1, 1)
    with patch("app.main.date") as mock_date:
        mock_date.today.return_value = mock_today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        # Recent work (2024) - 0.2 decades ago
        decades = _calculate_decades_since_most_recent_work(2024)
        assert 0.1 < decades < 0.3, f"Expected ~0.2 decades, got {decades}"

        # Older work (2000) - ~2.6 decades ago
        decades = _calculate_decades_since_most_recent_work(2000)
        assert 2.5 < decades < 2.7, f"Expected ~2.6 decades, got {decades}"


def test_calculate_decades_since_most_recent_work_with_string():
    """Regression: most recent work year as string should be converted to int."""
    from datetime import date
    from unittest.mock import patch

    from app.main import _calculate_decades_since_most_recent_work

    # Mock date.today() to return a fixed date for deterministic testing
    mock_today = date(2026, 1, 1)
    with patch("app.main.date") as mock_date:
        mock_date.today.return_value = mock_today
        mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)

        # Test string year - should convert to int and calculate correctly
        decades = _calculate_decades_since_most_recent_work("2024")
        assert 0.1 < decades < 0.3, f"Expected ~0.2 decades from string '2024', got {decades}"

        decades = _calculate_decades_since_most_recent_work("2000")
        assert 2.5 < decades < 2.7, f"Expected ~2.6 decades from string '2000', got {decades}"


def test_calculate_decades_since_most_recent_work_with_none():
    """When year is None, should return default midpoint."""
    from app.main import DEFAULT_RECENCY_DECADES, _calculate_decades_since_most_recent_work

    decades = _calculate_decades_since_most_recent_work(None)
    assert decades == DEFAULT_RECENCY_DECADES


# ---------------------------------------------------------------------------
# Regression tests for graph_db service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_most_recent_work_year_converts_strings_to_int():
    """Regression: get_most_recent_work_year should convert string years to int for numeric comparison.

    Previously, the code extracted years as strings and passed them to max(),
    which resulted in lexicographic comparison instead of numeric comparison.
    For example, max(["1973", "2020", "1999"]) would incorrectly return "2020"
    as a string. This test ensures the method converts to integers first.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.graph_db import GraphDBClient

    # Create a fresh instance for testing
    client = GraphDBClient()

    # Mock response from /viz/author-network with year values as strings
    mock_response = {
        "nodes": [
            {"id": "work_1", "group": "work", "year": "1973"},
            {"id": "work_2", "group": "work", "year": "2020"},
            {"id": "work_3", "group": "work", "year": "1999"},
            {"id": "author_1", "group": "author", "year": None},
        ],
        "edges": [],
    }

    # Create proper async mock for the response
    mock_response_obj = MagicMock()
    mock_response_obj.json.return_value = mock_response
    mock_response_obj.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response_obj
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    # Patch AsyncClient in the graph_db module
    with patch("app.services.graph_db.httpx.AsyncClient", return_value=mock_client):
        result = await client.get_most_recent_work_year("author_test_id")
        assert result == 2020, f"Expected 2020 but got {result}"


@pytest.mark.asyncio
async def test_get_most_recent_work_year_with_missing_years():
    """get_most_recent_work_year should return None when no work years are available."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.graph_db import GraphDBClient

    # Create a fresh instance for testing
    client = GraphDBClient()

    # Mock response with no work nodes that have years
    mock_response = {
        "nodes": [
            {"id": "author_1", "group": "author", "year": None},
            {"id": "org_1", "group": "organization", "year": None},
        ],
        "edges": [],
    }

    # Create proper async mock for the response
    mock_response_obj = MagicMock()
    mock_response_obj.json.return_value = mock_response
    mock_response_obj.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response_obj
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    # Patch AsyncClient in the graph_db module
    with patch("app.services.graph_db.httpx.AsyncClient", return_value=mock_client):
        result = await client.get_most_recent_work_year("author_test_id")
        assert result is None, f"Expected None but got {result}"


# ---------------------------------------------------------------------------
# graph_db.py — get_most_recent_work_year error paths (lines 51-56)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_most_recent_work_year_http_error():
    """HTTPError from graph DB should return None gracefully."""
    from app.services.graph_db import GraphDBClient
    client = GraphDBClient()
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get.side_effect = httpx.RequestError("connection refused")
        mock_client_class.return_value = mock_instance
        result = await client.get_most_recent_work_year("author_1a2b3c4d-1234-5678-abcd-1234567890ab")
    assert result is None


@pytest.mark.asyncio
async def test_get_most_recent_work_year_unexpected_error():
    """Unexpected exception from graph DB should return None gracefully."""
    from app.services.graph_db import GraphDBClient
    client = GraphDBClient()
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_instance.get.side_effect = RuntimeError("unexpected")
        mock_client_class.return_value = mock_instance
        result = await client.get_most_recent_work_year("author_1a2b3c4d-1234-5678-abcd-1234567890ab")
    assert result is None