"""Tests for the vector-loader job."""
import gzip
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import httpx
import pytest

from app.loader import VectorDBClient, VectorLoader
from app.config import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_gz_jsonl(path: Path, records: list) -> Path:
    """Write a list of dicts to a gzip'd JSONL file."""
    with gzip.open(path, "wb") as fh:
        for record in records:
            fh.write((json.dumps(record) + "\n").encode("utf-8"))
    return path


def make_loader(tmp_path: Path, mock_client: MagicMock = None) -> VectorLoader:
    """Create a VectorLoader with an injected mock client and tmp data dir."""
    if mock_client is None:
        mock_client = MagicMock()
    return VectorLoader(client=mock_client, data_dir=tmp_path)


# ===========================================================================
# VectorDBClient
# ===========================================================================

class TestVectorDBClient:

    def test_check_health_success(self):
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_cls.return_value = mock_http
            mock_http.get.return_value.json.return_value = {"status": "healthy"}

            client = VectorDBClient("http://test:8002")
            assert client.check_health() is True

    def test_check_health_unhealthy_status(self):
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_cls.return_value = mock_http
            mock_http.get.return_value.json.return_value = {"status": "unhealthy"}

            client = VectorDBClient("http://test:8002")
            assert client.check_health() is False

    def test_check_health_exception(self):
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_cls.return_value = mock_http
            mock_http.get.side_effect = Exception("Connection refused")

            client = VectorDBClient("http://test:8002")
            assert client.check_health() is False

    def test_get_collection_info_success(self):
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_cls.return_value = mock_http
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"name": "test", "num_entities": 100}
            mock_http.get.return_value = mock_resp

            client = VectorDBClient("http://test:8002")
            info = client.get_collection_info("my_collection")

            assert info == {"name": "test", "num_entities": 100}

    def test_get_collection_info_not_found(self):
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_cls.return_value = mock_http
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_http.get.return_value = mock_resp

            client = VectorDBClient("http://test:8002")
            info = client.get_collection_info("missing")

            assert info is None

    def test_get_collection_info_exception(self):
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_cls.return_value = mock_http
            mock_http.get.side_effect = Exception("Network error")

            client = VectorDBClient("http://test:8002")
            assert client.get_collection_info("any") is None

    def test_create_author_embedding_success(self):
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_cls.return_value = mock_http
            mock_http.post.return_value.raise_for_status.return_value = None

            client = VectorDBClient("http://test:8002")
            ok = client.create_author_embedding(
                "a1", "Alice", ["abstract"], "col", "model", citation_count=5
            )
            assert ok is True

    def test_create_author_embedding_no_citation_count(self):
        """citation_count=None must be excluded from the request payload."""
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_cls.return_value = mock_http
            mock_http.post.return_value.raise_for_status.return_value = None

            client = VectorDBClient("http://test:8002")
            ok = client.create_author_embedding(
                "a1", "Alice", ["text"], "col", "model", citation_count=None
            )

            assert ok is True
            payload = mock_http.post.call_args.kwargs["json"]
            assert "citation_count" not in payload

    def test_create_author_embedding_http_status_error(self):
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_cls.return_value = mock_http
            mock_resp = MagicMock()
            mock_resp.text = "Bad Request"
            mock_http.post.return_value.raise_for_status.side_effect = (
                httpx.HTTPStatusError("400", request=MagicMock(), response=mock_resp)
            )

            client = VectorDBClient("http://test:8002")
            assert client.create_author_embedding("a1", "Alice", ["text"], "col", "model") is False

    def test_create_author_embedding_general_exception(self):
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_cls.return_value = mock_http
            mock_http.post.side_effect = Exception("Timeout")

            client = VectorDBClient("http://test:8002")
            assert client.create_author_embedding("a1", "Alice", ["text"], "col", "model") is False

    def test_close(self):
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_cls.return_value = mock_http

            client = VectorDBClient("http://test:8002")
            client.close()
            mock_http.close.assert_called_once()


# ===========================================================================
# VectorLoader._parse_json
# ===========================================================================

class TestParseJson:

    def test_parse_json_without_orjson(self, tmp_path):
        loader = make_loader(tmp_path)
        with patch("app.loader.HAS_ORJSON", False):
            result = loader._parse_json(b'{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_with_orjson(self, tmp_path):
        loader = make_loader(tmp_path)
        with patch("app.loader.HAS_ORJSON", True):
            result = loader._parse_json(b'{"key": "value"}')
        assert result == {"key": "value"}


# ===========================================================================
# VectorLoader.should_skip_loading
# ===========================================================================

class TestShouldSkipLoading:

    def test_returns_false_when_skip_if_loaded_disabled(self, tmp_path):
        mock_client = MagicMock()
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings") as s:
            s.skip_if_loaded = False
            assert loader.should_skip_loading() is False

        mock_client.get_collection_info.assert_not_called()

    def test_returns_true_when_above_threshold(self, tmp_path):
        mock_client = MagicMock()
        mock_client.get_collection_info.return_value = {"num_entities": 500}
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings") as s:
            s.skip_if_loaded = True
            s.collection_name = "col"
            s.min_entities_threshold = 100
            assert loader.should_skip_loading() is True

    def test_returns_false_when_below_threshold(self, tmp_path):
        mock_client = MagicMock()
        mock_client.get_collection_info.return_value = {"num_entities": 10}
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings") as s:
            s.skip_if_loaded = True
            s.collection_name = "col"
            s.min_entities_threshold = 100
            assert loader.should_skip_loading() is False

    def test_returns_false_when_no_collection(self, tmp_path):
        mock_client = MagicMock()
        mock_client.get_collection_info.return_value = None
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings") as s:
            s.skip_if_loaded = True
            s.collection_name = "col"
            s.min_entities_threshold = 100
            assert loader.should_skip_loading() is False


# ===========================================================================
# VectorLoader.get_compressed_files
# ===========================================================================

class TestGetCompressedFiles:

    def test_returns_matching_files(self, tmp_path):
        (tmp_path / "dtic_works_001.jsonl.gz").touch()
        (tmp_path / "dtic_works_002.jsonl.gz").touch()
        (tmp_path / "dtic_authors_001.jsonl.gz").touch()

        loader = make_loader(tmp_path)
        files = loader.get_compressed_files("works")

        assert len(files) == 2
        assert all("works" in f.name for f in files)

    def test_returns_empty_when_no_match(self, tmp_path):
        loader = make_loader(tmp_path)
        assert loader.get_compressed_files("topics") == []


# ===========================================================================
# VectorLoader.build_author_lookup
# ===========================================================================

class TestBuildAuthorLookup:

    def test_returns_empty_when_no_files(self, tmp_path):
        loader = make_loader(tmp_path)
        assert loader.build_author_lookup() == {}

    def test_builds_lookup_from_files(self, tmp_path):
        records = [
            {"id": "A1", "name": "Alice Smith", "citation_count": 42},
            {"id": "A2", "name": "Bob Jones", "citation_count": 10},
        ]
        make_gz_jsonl(tmp_path / "dtic_authors_001.jsonl.gz", records)

        loader = make_loader(tmp_path)
        lookup = loader.build_author_lookup()

        assert lookup["A1"] == {"name": "Alice Smith", "citation_count": 42}
        assert lookup["A2"] == {"name": "Bob Jones", "citation_count": 10}

    def test_uses_id_as_name_when_name_missing(self, tmp_path):
        make_gz_jsonl(tmp_path / "dtic_authors_001.jsonl.gz", [{"id": "A3"}])

        loader = make_loader(tmp_path)
        lookup = loader.build_author_lookup()

        assert lookup["A3"]["name"] == "A3"

    def test_skips_records_without_id(self, tmp_path):
        make_gz_jsonl(tmp_path / "dtic_authors_001.jsonl.gz", [{"name": "No ID"}])

        loader = make_loader(tmp_path)
        assert loader.build_author_lookup() == {}

    def test_skips_blank_lines(self, tmp_path):
        gz_path = tmp_path / "dtic_authors_001.jsonl.gz"
        with gzip.open(gz_path, "wb") as fh:
            fh.write(b"\n")
            fh.write(b'{"id": "A1", "name": "Alice"}\n')
            fh.write(b"   \n")

        loader = make_loader(tmp_path)
        assert "A1" in loader.build_author_lookup()

    def test_skips_corrupt_records(self, tmp_path):
        gz_path = tmp_path / "dtic_authors_001.jsonl.gz"
        with gzip.open(gz_path, "wb") as fh:
            fh.write(b'{"id": "A1", "name": "Good"}\n')
            fh.write(b"NOT VALID JSON\n")
            fh.write(b'{"id": "A2", "name": "Also Good"}\n')

        loader = make_loader(tmp_path)
        lookup = loader.build_author_lookup()
        assert "A1" in lookup and "A2" in lookup

    def test_skips_unreadable_file(self, tmp_path):
        (tmp_path / "dtic_authors_bad.jsonl.gz").write_bytes(b"not a gzip file")

        loader = make_loader(tmp_path)
        lookup = loader.build_author_lookup()  # must not raise
        assert isinstance(lookup, dict)

    def test_deduplicates_authors_across_files(self, tmp_path):
        make_gz_jsonl(tmp_path / "dtic_authors_001.jsonl.gz", [{"id": "A1", "name": "Alice"}])
        make_gz_jsonl(tmp_path / "dtic_authors_002.jsonl.gz", [{"id": "A1", "name": "Alice v2"}])

        loader = make_loader(tmp_path)
        lookup = loader.build_author_lookup()
        # Last write wins; just verify A1 is present
        assert "A1" in lookup


# ===========================================================================
# VectorLoader.process_works_file
# ===========================================================================

def _settings_stub(max_records=None, collection="col", model="mdl"):
    """Return a minimal settings mock for process_works_file."""
    s = MagicMock()
    s.max_records = max_records
    s.collection_name = collection
    s.embedding_model = model
    return s


class TestProcessWorksFile:

    def test_uploads_authors_from_works(self, tmp_path):
        works = [{"abstract": "Deep learning research", "authors": [{"author_id": "A1"}, {"author_id": "A2"}]}]
        gz = make_gz_jsonl(tmp_path / "dtic_works_001.jsonl.gz", works)

        mock_client = MagicMock()
        mock_client.create_author_embedding.return_value = True
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings", _settings_stub()):
            count = loader.process_works_file(gz, {"A1": {"name": "Alice", "citation_count": 5}})

        assert count == 1
        assert mock_client.create_author_embedding.call_count == 2

    def test_skips_works_without_abstract(self, tmp_path):
        gz = make_gz_jsonl(tmp_path / "dtic_works_001.jsonl.gz",
                           [{"abstract": "", "authors": [{"author_id": "A1"}]}])

        mock_client = MagicMock()
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings", _settings_stub()):
            loader.process_works_file(gz, {})

        mock_client.create_author_embedding.assert_not_called()

    def test_skips_authors_without_id(self, tmp_path):
        gz = make_gz_jsonl(tmp_path / "dtic_works_001.jsonl.gz",
                           [{"abstract": "Valid text", "authors": [{"no_id": "X"}]}])

        mock_client = MagicMock()
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings", _settings_stub()):
            loader.process_works_file(gz, {})

        mock_client.create_author_embedding.assert_not_called()

    def test_respects_max_records(self, tmp_path):
        works = [{"abstract": f"Abstract {i}", "authors": [{"author_id": "A1"}]} for i in range(5)]
        gz = make_gz_jsonl(tmp_path / "dtic_works_001.jsonl.gz", works)

        mock_client = MagicMock()
        mock_client.create_author_embedding.return_value = True
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings", _settings_stub(max_records=2)):
            count = loader.process_works_file(gz, {})

        assert count == 2

    def test_counts_upload_failures(self, tmp_path):
        works = [{"abstract": "Research", "authors": [{"author_id": "A1"}, {"author_id": "A2"}]}]
        gz = make_gz_jsonl(tmp_path / "dtic_works_001.jsonl.gz", works)

        mock_client = MagicMock()
        mock_client.create_author_embedding.return_value = False
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings", _settings_stub()):
            loader.process_works_file(gz, {})

        assert loader.stats["authors_failed"] == 2

    def test_counts_exception_during_upload_as_failure(self, tmp_path):
        works = [{"abstract": "Research", "authors": [{"author_id": "A1"}]}]
        gz = make_gz_jsonl(tmp_path / "dtic_works_001.jsonl.gz", works)

        mock_client = MagicMock()
        mock_client.create_author_embedding.side_effect = Exception("upload boom")
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings", _settings_stub()):
            loader.process_works_file(gz, {})

        assert loader.stats["authors_failed"] == 1

    def test_handles_corrupt_record(self, tmp_path):
        gz_path = tmp_path / "dtic_works_001.jsonl.gz"
        with gzip.open(gz_path, "wb") as fh:
            fh.write(b"NOT_JSON\n")
            fh.write(b'{"abstract": "Good", "authors": [{"author_id": "A1"}]}\n')

        mock_client = MagicMock()
        mock_client.create_author_embedding.return_value = True
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings", _settings_stub()):
            count = loader.process_works_file(gz_path, {})

        assert count == 1  # only the valid record

    def test_returns_zero_on_file_open_error(self, tmp_path):
        bad_path = tmp_path / "dtic_works_bad.jsonl.gz"
        bad_path.write_bytes(b"not gzip")

        loader = make_loader(tmp_path)

        with patch("app.loader.settings", _settings_stub()):
            count = loader.process_works_file(bad_path, {})

        assert count == 0

    def test_updates_stats(self, tmp_path):
        works = [{"abstract": "Abstract", "authors": [{"author_id": "A1"}]}]
        gz = make_gz_jsonl(tmp_path / "dtic_works_001.jsonl.gz", works)

        mock_client = MagicMock()
        mock_client.create_author_embedding.return_value = True
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings", _settings_stub()):
            loader.process_works_file(gz, {})

        assert loader.stats["works_files_processed"] == 1
        assert loader.stats["works_records_read"] == 1
        assert loader.stats["authors_uploaded"] == 1

    def test_resolves_author_name_from_lookup(self, tmp_path):
        works = [{"abstract": "AI research", "authors": [{"author_id": "A1"}]}]
        gz = make_gz_jsonl(tmp_path / "dtic_works_001.jsonl.gz", works)

        mock_client = MagicMock()
        mock_client.create_author_embedding.return_value = True
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings", _settings_stub()):
            loader.process_works_file(gz, {"A1": {"name": "Dr. Alice", "citation_count": 99}})

        kwargs = mock_client.create_author_embedding.call_args.kwargs
        assert kwargs["author_name"] == "Dr. Alice"
        assert kwargs["citation_count"] == 99

    def test_falls_back_to_id_when_author_not_in_lookup(self, tmp_path):
        works = [{"abstract": "Research", "authors": [{"author_id": "UNKNOWN"}]}]
        gz = make_gz_jsonl(tmp_path / "dtic_works_001.jsonl.gz", works)

        mock_client = MagicMock()
        mock_client.create_author_embedding.return_value = True
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings", _settings_stub()):
            loader.process_works_file(gz, {})

        kwargs = mock_client.create_author_embedding.call_args.kwargs
        assert kwargs["author_name"] == "UNKNOWN"

    def test_progress_logging_every_10_authors(self, tmp_path):
        """Progress log fires every 10 authors — ensure no crash with exactly 10."""
        # 1 work referencing 10 distinct authors
        authors = [{"author_id": f"A{i}"} for i in range(10)]
        works = [{"abstract": "ML research", "authors": authors}]
        gz = make_gz_jsonl(tmp_path / "dtic_works_001.jsonl.gz", works)

        mock_client = MagicMock()
        mock_client.create_author_embedding.return_value = True
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings", _settings_stub()):
            loader.process_works_file(gz, {})

        assert loader.stats["authors_uploaded"] == 10


# ===========================================================================
# VectorLoader.process_entity_type
# ===========================================================================

class TestProcessEntityType:

    def test_no_files_logs_warning_without_raising(self, tmp_path):
        loader = make_loader(tmp_path)
        loader.process_entity_type("works", {})  # no gz files → should not crash

    def test_processes_works_files(self, tmp_path):
        works = [{"abstract": "Research", "authors": [{"author_id": "A1"}]}]
        make_gz_jsonl(tmp_path / "dtic_works_001.jsonl.gz", works)

        mock_client = MagicMock()
        mock_client.create_author_embedding.return_value = True
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.settings", _settings_stub()):
            loader.process_entity_type("works", {})

        assert loader.stats["works_files_processed"] == 1

    def test_unsupported_entity_type_is_skipped(self, tmp_path):
        make_gz_jsonl(tmp_path / "dtic_topics_001.jsonl.gz", [{"id": "t1"}])

        mock_client = MagicMock()
        loader = make_loader(tmp_path, mock_client)
        loader.process_entity_type("topics", {})

        mock_client.create_author_embedding.assert_not_called()


# ===========================================================================
# VectorLoader.run
# ===========================================================================

class TestVectorLoaderRun:

    def test_raises_when_health_check_never_passes(self, tmp_path):
        mock_client = MagicMock()
        mock_client.check_health.return_value = False
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.time.sleep"):
            with pytest.raises(RuntimeError, match="health check"):
                loader.run()

        mock_client.close.assert_called_once()

    def test_skips_loading_when_data_already_present(self, tmp_path):
        mock_client = MagicMock()
        mock_client.check_health.return_value = True
        loader = make_loader(tmp_path, mock_client)

        with patch.object(loader, "should_skip_loading", return_value=True), \
             patch.object(loader, "build_author_lookup") as mock_lookup, \
             patch.object(loader, "process_entity_type") as mock_process:
            loader.run()

        mock_lookup.assert_not_called()
        mock_process.assert_not_called()
        mock_client.close.assert_called_once()

    def test_run_full_pipeline(self, tmp_path):
        mock_client = MagicMock()
        mock_client.check_health.return_value = True
        loader = make_loader(tmp_path, mock_client)

        fake_lookup = {"A1": {"name": "Alice", "citation_count": 0}}

        with patch.object(loader, "should_skip_loading", return_value=False), \
             patch.object(loader, "build_author_lookup", return_value=fake_lookup), \
             patch.object(loader, "process_entity_type") as mock_process:
            loader.run()

        mock_process.assert_called_once_with("works", fake_lookup)
        mock_client.close.assert_called_once()

    def test_close_called_even_after_exception(self, tmp_path):
        """The finally block must call client.close() even on unexpected failure."""
        mock_client = MagicMock()
        mock_client.check_health.return_value = True
        loader = make_loader(tmp_path, mock_client)

        with patch.object(loader, "should_skip_loading", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                loader.run()

        mock_client.close.assert_called_once()

    def test_health_check_passes_after_retry(self, tmp_path):
        """Loader succeeds when health check passes on second attempt."""
        mock_client = MagicMock()
        mock_client.check_health.side_effect = [False, True]
        loader = make_loader(tmp_path, mock_client)

        with patch("app.loader.time.sleep"), \
             patch.object(loader, "should_skip_loading", return_value=True):
            loader.run()  # should not raise

        assert mock_client.check_health.call_count == 2


# ===========================================================================
# main()
# ===========================================================================

def test_main():
    with patch("app.loader.VectorLoader") as mock_cls:
        mock_loader = MagicMock()
        mock_cls.return_value = mock_loader

        from app.loader import main
        main()

        mock_cls.assert_called_once()
        mock_loader.run.assert_called_once()

