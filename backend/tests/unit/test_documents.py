"""Unit tests for document listing and catalog-backed management endpoints."""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import AppSettings, get_settings
from app.schemas.documents import (
    DocumentMetadata,
    DocumentStatus,
    DocumentSummary,
)
from radia_ai.features.jama_requirement_reviewer.dependencies.container import (
    get_document_catalog_repository,
    get_search_service,
)


class _StubDocumentCatalog:
    def __init__(self) -> None:
        self.document = DocumentSummary(
            document_id="a" * 64,
            filename="requirements.pdf",
            status=DocumentStatus.INDEXED,
            chunk_count=2,
            metadata=DocumentMetadata(
                source="sharepoint",
                filename="requirements.pdf",
                document_type="reference",
            ),
        )
        self.list_arguments: dict[str, Any] = {}
        self.deleted: list[str] = []

    def list(self, **kwargs: Any) -> tuple[list[DocumentSummary], int]:
        self.list_arguments = kwargs
        return [self.document], 1

    def get(self, document_id: str) -> DocumentSummary | None:
        return self.document if document_id == self.document.document_id else None

    def delete(self, document_id: str) -> None:
        self.deleted.append(document_id)


class _StubSearchService:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def get_document_chunks(self, _document_id: str) -> list[dict[str, Any]]:
        return [
            {
                "chunk_id": "chunk-1",
                "content": "First indexed chunk",
                "chunk_index": 0,
                "page_number": 1,
                "section": "1",
            }
        ]

    def delete_documents_by_file_hash(self, document_id: str) -> None:
        self.deleted.append(document_id)


def _install_stubs(client: TestClient) -> tuple[_StubDocumentCatalog, _StubSearchService]:
    catalog = _StubDocumentCatalog()
    search = _StubSearchService()
    app = client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_document_catalog_repository] = lambda: catalog
    app.dependency_overrides[get_search_service] = lambda: search
    return catalog, search


def _remove_stubs(client: TestClient) -> None:
    app = client.app
    assert isinstance(app, FastAPI)
    app.dependency_overrides.pop(get_document_catalog_repository, None)
    app.dependency_overrides.pop(get_search_service, None)


@pytest.mark.unit
def test_list_documents_uses_catalog_filters_and_paging(client: TestClient) -> None:
    catalog, _ = _install_stubs(client)
    try:
        response = client.get(
            "/api/v1/documents",
            params={
                "page": 2,
                "page_size": 10,
                "source": "sharepoint",
                "query": "requirements",
                "sort_by": "chunk_count",
                "sort_order": "desc",
            },
        )
    finally:
        _remove_stubs(client)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["data"][0]["filename"] == "requirements.pdf"
    assert catalog.list_arguments == {
        "page": 2,
        "page_size": 10,
        "source": "sharepoint",
        "query": "requirements",
        "sort_by": "chunk_count",
        "sort_order": "desc",
    }


@pytest.mark.unit
def test_list_documents_validates_page_size(client: TestClient) -> None:
    _install_stubs(client)
    try:
        response = client.get("/api/v1/documents", params={"page_size": 101})
    finally:
        _remove_stubs(client)
    assert response.status_code == 422


@pytest.mark.unit
def test_get_document_returns_chunks_and_metadata(client: TestClient) -> None:
    catalog, _ = _install_stubs(client)
    try:
        response = client.get(f"/api/v1/documents/{catalog.document.document_id}")
    finally:
        _remove_stubs(client)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["metadata"]["source"] == "sharepoint"
    assert data["chunks"][0]["content"] == "First indexed chunk"


@pytest.mark.unit
def test_delete_document_removes_indexed_copy_only(client: TestClient) -> None:
    catalog, search = _install_stubs(client)
    try:
        response = client.delete(f"/api/v1/documents/{catalog.document.document_id}")
    finally:
        _remove_stubs(client)

    assert response.status_code == 200
    assert search.deleted == [catalog.document.document_id]
    assert catalog.deleted == [catalog.document.document_id]
    assert "source file was not changed" in response.json()["message"]


@pytest.mark.unit
def test_delete_document_is_disabled_outside_local_and_development(
    client: TestClient, test_settings: AppSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog, search = _install_stubs(client)
    app = client.app
    assert isinstance(app, FastAPI)
    monkeypatch.setitem(
        app.dependency_overrides,
        get_settings,
        lambda: test_settings.model_copy(update={"environment": "production"}),
    )
    try:
        response = client.delete(f"/api/v1/documents/{catalog.document.document_id}")
    finally:
        _remove_stubs(client)

    assert response.status_code == 503
    assert search.deleted == []
    assert catalog.deleted == []
