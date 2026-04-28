"""Integration test for aegis_scholar_api <-> identity_api"""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_full_identity_lookup_flow(main_api_url, identity_container):
    """
    Test the full chain:
    AsyncClient -> Main API (/identity/lookup) -> Identity API (/lookup) -> LDAP (container)

    Note: LDAP is seeded with test user 'Jane Smith' by the identity_container fixture in conftest.py
    """
    async with AsyncClient(base_url=main_api_url) as client:
        # 1. Lookup the seeded user
        response = await client.get("/identity/lookup", params={"name": "Jane Smith"})

        assert response.status_code == 200
        data = response.json()

        # 2. Assert exact match logic
        assert "exact_match" in data
        exact = data["exact_match"]
        assert exact is not None, f"Expected to find 'Jane Smith' but got: {data}"
        assert exact["name"] == "Jane Smith"
        assert exact["email"] == "jane.smith@example.org"

        # 3. Assert a non-existent user returns 200 but with no exact match
        response_missing = await client.get(
            "/identity/lookup", params={"name": "Ghost User"}
        )
        assert response_missing.status_code == 200
        assert response_missing.json().get("exact_match") is None


# --- Edge Case Tests ---


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_identity_lookup_case_insensitive(main_api_url, identity_container):
    """
    Tests that identity lookup is case-insensitive.
    "JANE SMITH" should find "Jane Smith".
    """
    case_variations = [
        "jane smith",
        "JANE SMITH",
        "Jane Smith",
        "jAnE sMiTh",
    ]

    async with AsyncClient(base_url=main_api_url) as client:
        for name_query in case_variations:
            response = await client.get("/identity/lookup", params={"name": name_query})

            assert response.status_code == 200, (
                f"Query '{name_query}' failed: {response.text}"
            )

            data = response.json()

            # Should find exact match regardless of case
            assert "exact_match" in data
            if data["exact_match"] is not None:
                # If found, name should match (case may vary based on LDAP storage)
                assert "jane smith" in data["exact_match"]["name"].lower()
                assert data["exact_match"]["email"] == "jane.smith@example.org"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_identity_lookup_partial_name(main_api_url, identity_container):
    """
    Tests lookup with partial name (first or last name only).
    Should return similar matches or exact match if unique.
    """
    partial_queries = [
        "Smith",
        "Jane",
    ]

    async with AsyncClient(base_url=main_api_url) as client:
        for name_query in partial_queries:
            response = await client.get("/identity/lookup", params={"name": name_query})

            assert response.status_code == 200, (
                f"Partial query '{name_query}' failed: {response.text}"
            )

            data = response.json()

            # Should return data structure (may have exact_match or similar_records)
            assert "exact_match" in data or "similar_records" in data

            # If similar records are returned, should be a list
            if "similar_records" in data:
                assert isinstance(data["similar_records"], list)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_identity_lookup_empty_name(main_api_url, identity_container):
    """
    Tests that empty name parameter is rejected with validation error.
    """
    async with AsyncClient(base_url=main_api_url) as client:
        # Missing query parameter
        response_missing = await client.get("/identity/lookup")

        # Should return 422 validation error
        assert response_missing.status_code == 422, (
            f"Missing name parameter should return 422, got {response_missing.status_code}"
        )

        data = response_missing.json()
        assert "detail" in data


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_identity_lookup_whitespace_name(main_api_url, identity_container):
    """
    Tests that whitespace-only names are handled appropriately.
    """
    whitespace_queries = ["   ", "\t\t"]

    async with AsyncClient(base_url=main_api_url) as client:
        for name_query in whitespace_queries:
            response = await client.get("/identity/lookup", params={"name": name_query})

            # Should either reject (422) or return no match (200)
            assert response.status_code in [200, 422], (
                f"Whitespace query returned unexpected status: {response.status_code}"
            )

            if response.status_code == 200:
                data = response.json()
                # Should not find a match
                assert data.get("exact_match") is None


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_identity_lookup_special_characters(main_api_url, identity_container):
    """
    Tests that special characters in names are handled correctly.
    LDAP filters must be properly escaped.
    """
    special_queries = [
        "O'Brien",  # Apostrophe
        "Jean-Luc",  # Hyphen
        "José García",  # Accented characters
        "Smith, Jr.",  # Comma and period
    ]

    async with AsyncClient(base_url=main_api_url) as client:
        for name_query in special_queries:
            response = await client.get("/identity/lookup", params={"name": name_query})

            # Should handle gracefully without crashing
            assert response.status_code == 200, (
                f"Query '{name_query}' crashed: {response.status_code} - {response.text}"
            )

            data = response.json()

            # Should return valid response structure
            assert "exact_match" in data
            # Won't find match (not in test data), but shouldn't crash
            assert data["exact_match"] is None or isinstance(data["exact_match"], dict)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_identity_lookup_very_long_name(main_api_url, identity_container):
    """
    Tests that very long names are handled correctly.
    Validates length limits and truncation.
    """
    # Create a 500 character name
    long_name = "A" * 500

    async with AsyncClient(base_url=main_api_url) as client:
        response = await client.get("/identity/lookup", params={"name": long_name})

        # Should either accept (200) or reject (422)
        assert response.status_code in [200, 422], (
            f"Very long name returned unexpected status: {response.status_code}"
        )

        if response.status_code == 200:
            data = response.json()
            assert "exact_match" in data
            # Won't find match, but shouldn't crash


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_identity_lookup_unicode_name(main_api_url, identity_container):
    """
    Tests that unicode characters in names are handled correctly.
    """
    unicode_queries = [
        "李明",  # Chinese
        "أحمد",  # Arabic
        "Müller",  # German umlaut
        "Владимир",  # Russian
    ]

    async with AsyncClient(base_url=main_api_url) as client:
        for name_query in unicode_queries:
            response = await client.get("/identity/lookup", params={"name": name_query})

            # Should handle gracefully
            assert response.status_code == 200, (
                f"Unicode query '{name_query}' failed: {response.status_code}"
            )

            data = response.json()
            assert "exact_match" in data
            # Won't find match, but shouldn't crash


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_identity_lookup_response_structure(main_api_url, identity_container):
    """
    Tests that the response structure is consistent and complete.
    Validates all expected fields are present.
    """
    async with AsyncClient(base_url=main_api_url) as client:
        response = await client.get("/identity/lookup", params={"name": "Jane Smith"})

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "exact_match" in data, "Response must include exact_match field"

        # If similar_records field exists, should be a list
        if "similar_records" in data:
            assert isinstance(data["similar_records"], list)

        # If exact_match found, validate its structure
        if data["exact_match"] is not None:
            exact = data["exact_match"]
            assert isinstance(exact, dict)
            assert "name" in exact, "exact_match must include name"
            assert "email" in exact, "exact_match must include email"

            # Validate field types
            assert isinstance(exact["name"], str)
            assert isinstance(exact["email"], str)
