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
