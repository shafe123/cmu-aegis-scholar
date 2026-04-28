"""
Service-layer integration tests for identity service against a live OpenLDAP container.

These tests spin up both our identity service container and an OpenLDAP container,
then validate that our API correctly queries and returns identity data.
"""

import pytest
import httpx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.requires_docker
def test_identity_service_is_healthy(identity_api_url):
    """Our identity service should report healthy when LDAP is available."""
    response = httpx.get(f"{identity_api_url}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "identity"


@pytest.mark.integration
@pytest.mark.requires_docker
def test_lookup_returns_empty_for_unknown_name(identity_api_url):
    """Lookup for a name not in LDAP should return no exact match."""
    response = httpx.get(f"{identity_api_url}/lookup", params={"name": "Nobody Known"})
    assert response.status_code == 200
    data = response.json()
    assert data["exact_match"] is None


@pytest.mark.integration
@pytest.mark.requires_docker
def test_stats_endpoint(identity_api_url):
    """Stats endpoint should return LDAP population counts."""
    response = httpx.get(f"{identity_api_url}/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_in_ldap" in data
    assert "with_email" in data
    assert "without_email" in data
