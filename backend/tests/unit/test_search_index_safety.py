"""
Unit tests for ``SearchService.ensure_index`` - guards against automatic data loss.

``ensure_index`` runs on every application startup (including every serverless
cold start on Vercel), so it must never silently delete an existing, populated
index just because a transient error occurred while updating its schema.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

from app.core.azure_clients import SearchService

if TYPE_CHECKING:
    from app.core.config import AppSettings


@pytest.mark.unit
def test_ensure_index_creates_when_missing(test_settings: AppSettings) -> None:
    """When the index does not exist yet, it is created without any deletion."""
    search_service = SearchService(
        test_settings.azure_search, openai_client=MagicMock(), app_settings=test_settings
    )
    search_service._index_client = MagicMock()
    search_service._index_client.get_index.side_effect = ResourceNotFoundError("not found")

    search_service.ensure_index()

    search_service._index_client.get_index.assert_called_once()
    search_service._index_client.create_or_update_index.assert_called_once()
    search_service._index_client.delete_index.assert_not_called()


@pytest.mark.unit
def test_ensure_index_updates_existing_without_deleting(test_settings: AppSettings) -> None:
    """When the index already exists and the update succeeds, nothing is deleted."""
    search_service = SearchService(
        test_settings.azure_search, openai_client=MagicMock(), app_settings=test_settings
    )
    search_service._index_client = MagicMock()
    search_service._index_client.get_index.return_value = MagicMock()

    search_service.ensure_index()

    search_service._index_client.create_or_update_index.assert_called_once()
    search_service._index_client.delete_index.assert_not_called()


@pytest.mark.unit
def test_ensure_index_never_deletes_on_update_failure(test_settings: AppSettings) -> None:
    """
    A schema-update failure (transient error, throttling, a concurrent cold start
    racing on the same PUT, etc.) must be raised, never silently handled by
    deleting the existing index - that would wipe every ingested document.
    """
    search_service = SearchService(
        test_settings.azure_search, openai_client=MagicMock(), app_settings=test_settings
    )
    search_service._index_client = MagicMock()
    search_service._index_client.get_index.return_value = MagicMock()
    search_service._index_client.create_or_update_index.side_effect = HttpResponseError(
        "schema conflict"
    )

    with pytest.raises(HttpResponseError):
        search_service.ensure_index()

    search_service._index_client.delete_index.assert_not_called()


@pytest.mark.unit
def test_upload_documents_uses_bounded_batches(test_settings: AppSettings) -> None:
    """Large document uploads stay below the Azure Search request-size limit."""
    search_service = SearchService(
        test_settings.azure_search, openai_client=MagicMock(), app_settings=test_settings
    )
    search_service._search_client = MagicMock()
    documents = [{"chunk_id": f"chunk-{index}"} for index in range(205)]
    search_service._search_client.upload_documents.side_effect = [
        [MagicMock(succeeded=True) for _ in range(100)],
        [MagicMock(succeeded=True) for _ in range(100)],
        [MagicMock(succeeded=True) for _ in range(5)],
    ]

    uploaded = search_service.upload_documents(documents)

    assert uploaded == 205
    batches = [
        call.kwargs["documents"]
        for call in search_service._search_client.upload_documents.call_args_list
    ]
    assert [len(batch) for batch in batches] == [100, 100, 5]
    assert [document for batch in batches for document in batch] == documents


@pytest.mark.unit
def test_upload_documents_stops_when_a_batch_fails(test_settings: AppSettings) -> None:
    """An Azure failure is surfaced without attempting later batches."""
    search_service = SearchService(
        test_settings.azure_search, openai_client=MagicMock(), app_settings=test_settings
    )
    search_service._search_client = MagicMock()
    documents = [{"chunk_id": f"chunk-{index}"} for index in range(205)]
    search_service._search_client.upload_documents.side_effect = [
        [MagicMock(succeeded=True) for _ in range(100)],
        HttpResponseError("Azure Search unavailable"),
    ]

    with pytest.raises(HttpResponseError):
        search_service.upload_documents(documents)

    assert search_service._search_client.upload_documents.call_count == 2
