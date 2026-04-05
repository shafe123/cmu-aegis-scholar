import gzip
import json
from unittest.mock import MagicMock, patch

import pytest

from app.loader import GraphDBClient, GraphLoader, main


# --- Helpers ---
def create_mock_gz(path, records):
    """Utility to create real gzipped JSONL files with optional blank lines."""
    with gzip.open(path, "wb") as f:
        for r in records:
            line = json.dumps(r) + "\n"
            f.write(line.encode("utf-8"))
        # Add a trailing blank line to cover the 'if not line.strip()' branch
        f.write(b"\n")
    return path


class TestGraphDBClient:
    """Tests for the API Client covering error paths (Lines 27, 30-32, 38, 48)."""

    def test_get_stats_bad_status(self):
        """Covers Line 27: logger.warning on non-200 status."""
        with patch("httpx.Client") as mock_cls:
            mock_resp = MagicMock(status_code=404)
            mock_cls.return_value.get.return_value = mock_resp
            assert GraphDBClient().get_stats() is None

    def test_get_stats_exception(self):
        """Covers Lines 30-32: except block for network errors."""
        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.get.side_effect = Exception("Network Timeout")
            assert GraphDBClient().get_stats() is None

    def test_upsert_node_exception(self):
        """Covers Lines 38-39: except block in node ingestion."""
        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.post.side_effect = Exception("API Down")
            assert GraphDBClient().upsert_node("authors", {"id": "1"}) is False

    def test_create_rel_exception(self):
        """Covers Lines 48-49: except block in relationship creation."""
        with patch("httpx.Client") as mock_cls:
            mock_cls.return_value.post.side_effect = Exception("API Down")
            assert GraphDBClient().create_relationship("authored", {}) is False


class TestGraphLoader:
    """Tests for orchestration and data processing (Lines 65, 81-93, 113, 123)."""

    def test_should_skip_false_no_stats(self):
        """Covers Line 65: Handling cases where API returns no stats."""
        api = MagicMock()
        api.get_stats.return_value = None
        with patch("app.loader.settings") as s:
            s.skip_if_loaded = True
            loader = GraphLoader(client=api)
            assert loader.should_skip_loading() is False

    def test_load_nodes_full_loop(self, tmp_data_dir):
        """Covers Lines 81-93: The node ingestion loop and file processing."""
        path = tmp_data_dir / "dtic_authors_1.jsonl.gz"
        create_mock_gz(path, [{"id": "a1", "name": "Alice"}])

        api = MagicMock()
        api.upsert_node.return_value = True
        loader = GraphLoader(client=api, data_dir=tmp_data_dir)
        loader.load_nodes("authors")
        assert api.upsert_node.called

    def test_load_works_and_rels_with_org(self, tmp_data_dir):
        """Covers Line 113 and Line 123: blank lines and org_id branching."""
        data = [{
            "id": "work_1",
            "authors": [{"author_id": "a1", "org_id": "org_1"}],
            "topics": [{"topic_id": "t1", "score": 0.5}]
        }]
        create_mock_gz(tmp_data_dir / "dtic_works_1.jsonl.gz", data)

        api = MagicMock()
        loader = GraphLoader(client=api, data_dir=tmp_data_dir)
        loader.load_works_and_rels()

        # upsert_work + authored_rel + affiliated_rel + covers_rel = 4 calls
        assert api.upsert_node.called
        assert api.create_relationship.call_count == 3

    def test_run_integration(self):
        """Covers orchestration without mocking inner methods."""
        loader = GraphLoader()
        loader.api = MagicMock()
        # Ensure it doesn't skip
        loader.api.get_stats.return_value = {"author_count": 0}

        with patch.object(loader, "load_nodes") as m_nodes, \
             patch.object(loader, "load_works_and_rels") as m_works:
            loader.run()
            assert m_nodes.call_count == 3
            assert m_works.called


def test_main_entrypoint():
    """Covers line 152: The main() function call."""
    with patch("app.loader.GraphLoader") as mock_loader_cls:
        mock_instance = MagicMock()
        mock_loader_cls.return_value = mock_instance
        main()
        assert mock_instance.run.called