"""Unit tests for SharePoint ingestion reconciliation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.ingestion.service import IngestionService


class StubSharePointClient:
    def __init__(self, files: list[dict[str, object]]) -> None:
        self._settings = SimpleNamespace(is_configured=True)
        self._files = files

    def fetch_file_contents(self) -> list[dict[str, object]]:
        return self._files


@pytest.mark.unit
def test_sharepoint_ingestion_removes_deleted_files(test_settings) -> None:
    search = MagicMock()
    search.get_indexed_files.return_value = {"deleted.pdf": {"deleted-hash"}}
    search.get_indexed_file_hashes.return_value = {"deleted-hash"}
    service = IngestionService(
        settings=test_settings,
        openai_client=MagicMock(),
        search_service=search,
        sharepoint_client=StubSharePointClient([]),
    )

    result = service.ingest_from_sharepoint()

    assert result["processed"] == 0
    assert result["skipped"] == 0
    search.delete_documents_by_file_hash.assert_called_once_with("deleted-hash")
    search.upload_documents.assert_not_called()


@pytest.mark.unit
def test_sharepoint_ingestion_replaces_old_revision_after_success(test_settings) -> None:
    search = MagicMock()
    search.get_indexed_files.return_value = {"guide.pdf": {"old-hash"}}
    search.get_indexed_file_hashes.return_value = {"old-hash"}
    service = IngestionService(
        settings=test_settings,
        openai_client=MagicMock(),
        search_service=search,
        sharepoint_client=StubSharePointClient(
            [{"name": "guide.pdf", "content": b"new content", "url": "", "document_type": ""}]
        ),
    )
    service._process_document = MagicMock()

    result = service.ingest_from_sharepoint()

    assert result["processed"] == 1
    search.delete_documents_by_file_hash.assert_called_once_with("old-hash")
