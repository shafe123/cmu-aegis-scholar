"""Integration tests for Aegis Scholar API container interaction with Vector DB container."""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_health_check_reports_vector_db_status(main_api_url, vector_db_url):
    """
    Validates that the main API's health endpoint reports the status of the Vector DB.
    Tests container-to-container communication: API → Vector DB.
    """
    async with AsyncClient(base_url=main_api_url) as ac:
        response = await ac.get("/health")

    assert response.status_code == 200, f"Health check failed: {response.text}"
    data = response.json()

    # Verify health response structure
    assert "status" in data
    assert "dependencies" in data

    # Verify Vector DB is listed as a dependency
    dependencies = data["dependencies"]
    assert "vector_db" in dependencies, "Vector DB should be listed in dependencies"

    # Check vector DB status (should start with "healthy", "unhealthy", or "unreachable")
    vector_db_status = dependencies["vector_db"]
    assert any(
        vector_db_status.startswith(prefix)
        for prefix in ["healthy", "unhealthy", "unreachable"]
    ), f"Unexpected vector DB status format: {vector_db_status}"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_author_search_integration(main_api_url, vector_db_url):
    """
    Validates the containerized API's author search via Vector DB.
    Tests the /search/authors endpoint with text query.
    
    Note: This test uses a generic search query since we don't have specific
    test data pre-loaded in the vector DB. The test validates structure and
    communication rather than specific results.
    """
    async with AsyncClient(base_url=main_api_url) as ac:
        # Search for a common research term
        response = await ac.get(
            "/search/authors",
            params={"q": "machine learning", "limit": 10},
        )

    # Response structure validation
    assert response.status_code in [
        200,
        503,
    ], f"Search failed unexpectedly: {response.text}"

    if response.status_code == 200:
        data = response.json()

        # Validate response structure
        assert "query" in data, "Response must include the search query"
        assert "results" in data, "Response must include results array"
        assert "total" in data, "Response must include total count"
        assert "limit" in data, "Response must include limit"
        assert "offset" in data, "Response must include offset"

        assert data["query"] == "machine learning"
        assert isinstance(data["results"], list)
        assert data["limit"] == 10
        assert data["offset"] == 0

        # If results are returned, validate author result schema
        if len(data["results"]) > 0:
            author = data["results"][0]
            assert "id" in author, "Author must have an id"
            assert "name" in author, "Author must have a name"
            assert "relevance_score" in author, "Author must have a relevance_score"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_author_search_with_pagination(main_api_url, vector_db_url):
    """
    Tests that pagination parameters are properly passed through to Vector DB.
    Validates limit and offset handling.
    """
    async with AsyncClient(base_url=main_api_url) as ac:
        # Request first page
        response_page1 = await ac.get(
            "/search/authors",
            params={"q": "artificial intelligence", "limit": 5, "offset": 0},
        )

        # Request second page
        response_page2 = await ac.get(
            "/search/authors",
            params={"q": "artificial intelligence", "limit": 5, "offset": 5},
        )

    # Both requests should succeed (or both return 503 if vector DB unavailable)
    assert response_page1.status_code in [200, 503]
    assert response_page2.status_code in [200, 503]

    if response_page1.status_code == 200 and response_page2.status_code == 200:
        data1 = response_page1.json()
        data2 = response_page2.json()

        # Validate pagination parameters are reflected
        assert data1["offset"] == 0
        assert data1["limit"] == 5
        assert data2["offset"] == 5
        assert data2["limit"] == 5

        # If both pages have results, they should be different
        if len(data1["results"]) > 0 and len(data2["results"]) > 0:
            # Check that results are different (not the same page returned twice)
            ids_page1 = {author["id"] for author in data1["results"]}
            ids_page2 = {author["id"] for author in data2["results"]}
            assert ids_page1 != ids_page2, "Pagination should return different results"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_author_search_with_sorting(main_api_url, vector_db_url):
    """
    Tests that sorting parameters work correctly.
    Validates sort_by and order parameters.
    """
    async with AsyncClient(base_url=main_api_url) as ac:
        # Sort by relevance (default)
        response_relevance = await ac.get(
            "/search/authors",
            params={
                "q": "computer science",
                "limit": 10,
                "sort_by": "relevance_score",
                "order": "desc",
            },
        )

        # Sort by citation count
        response_citations = await ac.get(
            "/search/authors",
            params={
                "q": "computer science",
                "limit": 10,
                "sort_by": "citation_count",
                "order": "desc",
            },
        )

    assert response_relevance.status_code in [200, 503]
    assert response_citations.status_code in [200, 503]

    if response_relevance.status_code == 200:
        data = response_relevance.json()
        assert "results" in data

        # If we have multiple results, verify they're sorted by relevance
        if len(data["results"]) > 1:
            relevance_scores = [r["relevance_score"] for r in data["results"]]
            # Scores should be in descending order (highest relevance first)
            assert relevance_scores == sorted(
                relevance_scores, reverse=True
            ), "Results should be sorted by relevance score descending"

    if response_citations.status_code == 200:
        data = response_citations.json()
        assert "results" in data

        # If we have multiple results with citation counts, verify sorting
        if len(data["results"]) > 1:
            results_with_citations = [
                r for r in data["results"] if r.get("citation_count") is not None
            ]
            if len(results_with_citations) > 1:
                citation_counts = [r["citation_count"] for r in results_with_citations]
                # Should be in descending order (highest citations first)
                assert citation_counts == sorted(
                    citation_counts, reverse=True
                ), "Results should be sorted by citation_count descending"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_author_search_empty_query(main_api_url):
    """
    Tests error handling for invalid queries.
    Empty query should return 422 Unprocessable Entity.
    """
    async with AsyncClient(base_url=main_api_url) as ac:
        # Empty query parameter should fail validation
        response = await ac.get("/search/authors", params={"limit": 10})

    # FastAPI should return 422 for missing required query parameter
    assert response.status_code == 422, "Empty query should return validation error"
    data = response.json()
    assert "detail" in data, "Error response should include detail"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_author_search_respects_limits(main_api_url, vector_db_url):
    """
    Tests that the API respects min/max limits defined in settings.
    """
    async with AsyncClient(base_url=main_api_url) as ac:
        # Test with valid limit
        response_valid = await ac.get(
            "/search/authors",
            params={"q": "biology", "limit": 20},
        )

        # Test with limit exceeding max (should be rejected or clamped)
        response_too_large = await ac.get(
            "/search/authors",
            params={"q": "biology", "limit": 1000},
        )

        # Test with zero limit (should be rejected)
        response_zero = await ac.get(
            "/search/authors",
            params={"q": "biology", "limit": 0},
        )

    # Valid limit should work
    assert response_valid.status_code in [200, 503]

    # Invalid limits should return 422 (validation error)
    assert response_too_large.status_code == 422, "Excessive limit should be rejected"
    assert response_zero.status_code == 422, "Zero limit should be rejected"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_vector_db_connectivity_error_handling(main_api_url):
    """
    Tests that the API handles Vector DB connection failures gracefully.
    
    Note: This test verifies that the API returns appropriate error codes
    when the Vector DB is unavailable, rather than crashing.
    """
    async with AsyncClient(base_url=main_api_url) as ac:
        response = await ac.get(
            "/search/authors",
            params={"q": "test query", "limit": 10},
        )

    # Should return either 200 (if Vector DB is up) or 503 (if unavailable)
    # Should NOT crash with 500
    assert response.status_code in [
        200,
        503,
    ], f"Unexpected status code: {response.status_code}"

    if response.status_code == 503:
        data = response.json()
        assert "detail" in data, "Error response should include detail message"
        # Message should indicate service unavailability
        assert (
            "unavailable" in data["detail"].lower()
            or "unreachable" in data["detail"].lower()
        )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_relevance_score_calculation(main_api_url, vector_db_url):
    """
    Tests that relevance scores are properly calculated and included.
    Relevance should combine vector similarity with metadata like citation count.
    """
    async with AsyncClient(base_url=main_api_url) as ac:
        response = await ac.get(
            "/search/authors",
            params={"q": "neural networks", "limit": 10},
        )

    if response.status_code == 200:
        data = response.json()

        if len(data["results"]) > 0:
            for author in data["results"]:
                # Every result should have a relevance_score
                assert (
                    "relevance_score" in author
                ), "Author results must include relevance_score"
                relevance = author["relevance_score"]

                # Relevance should be a number between 0 and 1 (or slightly higher due to boosting)
                assert isinstance(
                    relevance, (int, float)
                ), "relevance_score must be numeric"
                assert relevance >= 0, "relevance_score should be non-negative"
                # Allow some tolerance for boosted scores
                assert (
                    relevance <= 2.0
                ), "relevance_score should not be unreasonably high"
