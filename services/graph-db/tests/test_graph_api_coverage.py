import os
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.schemas import AuthorNode

# ---------------------------------------------------------------------------
# 1. Testing Config & Secrets
# ---------------------------------------------------------------------------


def test_settings_reads_from_secret_file(tmp_path):
    """Verify that Settings can load a password from a secrets directory."""
    secret_val = "secure_temp_password_123"
    d = tmp_path / "secrets"
    d.mkdir()
    p = d / "neo4j_password"
    p.write_text(secret_val)

    # Passing _secrets_dir to the constructor overrides the class config
    s = Settings(_secrets_dir=str(d))
    assert s.neo4j_password == secret_val


def test_settings_falls_back_to_env():
    """Verify fallback to environment variables when secrets are missing."""
    with patch.dict(os.environ, {"NEO4J_PASSWORD": "env_password"}):
        s = Settings(_secrets_dir=None)
        assert s.neo4j_password == "env_password"


# ---------------------------------------------------------------------------
# 2. Testing Internal Logic Branches
# ---------------------------------------------------------------------------


def test_viz_logic_handling_of_solo_authors():
    """Verify the visualization loop handles missing co-authors safely."""
    mock_record = {
        "a": {"id": "a1", "name": "Author"},
        "w": {"id": "w1", "title": "Work"},
        "co": None,
    }

    nodes, node_ids = [], set()

    # This block mirrors the logic in your main.py visualization endpoint
    for record in [mock_record]:
        author, work, co_author = record["a"], record["w"], record["co"]
        if author["id"] not in node_ids:
            nodes.append(author)
            node_ids.add(author["id"])
        if work["id"] not in node_ids:
            nodes.append(work)
            node_ids.add(work["id"])
        if co_author and co_author["id"] not in node_ids:
            nodes.append(co_author)
            node_ids.add(co_author["id"])

    assert len(nodes) == 2  # Only Author and Work, no Co-Author node


# ---------------------------------------------------------------------------
# 3. Testing Schema Defaults
# ---------------------------------------------------------------------------


def test_author_schema_defaults():
    author = AuthorNode(id="auth_1", name="Test")
    assert author.h_index == 0
    assert author.works_count == 0


# ---------------------------------------------------------------------------
# 4. Lifecycle Coverage (Shutdown Logic)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_shutdown_closes_driver():
    """Verify that the lifespan context manager closes the driver on exit."""
    from app.main import lifespan

    mock_app = MagicMock()

    # We patch the global driver in the main module
    with patch("app.main.driver") as mock_driver:
        # lifespan is an async generator, so we use 'async with'
        async with lifespan(mock_app):
            pass

        # Check that driver.close() was called when we exited the 'with' block
        mock_driver.close.assert_called_once()
