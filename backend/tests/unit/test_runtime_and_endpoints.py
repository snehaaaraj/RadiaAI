"""Unit tests for runtime config, auth helpers, search, and ingestion endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pytest
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from app.core.config import (
    AppSettings,
    AzureBlobSettings,
    AzureOpenAISettings,
    AzureSearchSettings,
    get_settings,
)
from app.core.security import _entra_auth, _stub_auth
from app.dependencies.container import get_ingestion_service, get_search_service

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def _make_request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})


@pytest.mark.unit
def test_get_settings_loads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-test")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "embedding-test")
    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "https://test.search.windows.net")
    monkeypatch.setenv("AZURE_SEARCH_API_KEY", "test-key")
    monkeypatch.setenv(
        "AZURE_BLOB_CONNECTION_STRING",
        "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net",
    )
    monkeypatch.setenv("SHAREPOINT_TENANT_ID", "tenant")
    monkeypatch.setenv("SHAREPOINT_CLIENT_ID", "client")
    monkeypatch.setenv("SHAREPOINT_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SHAREPOINT_SITE_URL", "https://example.sharepoint.com/sites/demo")
    monkeypatch.setenv("VITE_API_BASE_URL", "/api/v1")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.app_name == "Radia AI"
    assert settings.azure_openai.chat_deployment == "gpt-4o-test"
    assert settings.azure_search.index_name == "radia-documents"
    assert settings.sharepoint.is_configured is True


@pytest.mark.unit
def test_app_settings_rejects_debug_in_production() -> None:
    with pytest.raises(ValueError):
        AppSettings(
            environment="production",
            debug=True,
            log_level="INFO",
            azure_openai=AzureOpenAISettings.model_construct(
                endpoint="https://test.openai.azure.com",
                api_key="test-key",
                chat_deployment="gpt-4o-test",
                embedding_deployment="embedding-test",
            ),
            azure_search=AzureSearchSettings.model_construct(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
            ),
            azure_blob=AzureBlobSettings.model_construct(
                connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;",
            ),
        )


@pytest.mark.asyncio
async def test_stub_auth_returns_synthetic_user() -> None:
    user = await _stub_auth(_make_request(), credentials=None)

    assert user.user_id == "local-dev-user"
    assert user.email == "dev@radia.local"
    assert user.has_role("admin") is True


@pytest.mark.asyncio
async def test_entra_auth_requires_credentials() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await _entra_auth(_make_request(), credentials=None)

    assert exc_info.value.status_code == 401


@dataclass
class DummySearchService:
    calls: list[tuple[str, str, int | None, dict[str, str] | None]]

    def search(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        top_k: int | None = None,
        filters: dict[str, str] | None = None,
    ) -> list[dict[str, object]]:
        self.calls.append((query, mode, top_k, filters))
        return [
            {
                "chunk_id": "chunk-1",
                "score": 0.97,
                "source": "sharepoint",
                "filename": "standards.docx",
                "document_type": "reference",
                "section": "1",
                "page_number": 2,
                "content": "Example content",
                "highlights": ["Example content"],
            }
        ]


@dataclass
class DummyIngestionService:
    blob_calls: list[list[str] | None]
    sharepoint_calls: int
    raw_calls: list[tuple[bytes, str, str]]

    def ingest_from_blob(self, document_ids: list[str] | None = None) -> dict[str, int]:
        self.blob_calls.append(document_ids)
        return {"processed": 2, "skipped": 1, "failed": 0}

    def ingest_from_sharepoint(self) -> dict[str, int]:
        self.sharepoint_calls += 1
        return {"processed": 3, "skipped": 0, "failed": 0}

    def ingest_raw_document(
        self, data: bytes, filename: str, source: str = "upload"
    ) -> dict[str, str]:
        self.raw_calls.append((data, filename, source))
        return {"status": "indexed", "filename": filename}


@pytest.mark.unit
def test_search_endpoint_returns_structured_results(client: TestClient) -> None:
    dummy = DummySearchService(calls=[])
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_search_service] = lambda: dummy
    try:
        response = client.post(
            "/api/v1/search",
            json={
                "query": "wing structure",
                "mode": "hybrid",
                "top_k": 5,
                "filters": {"document_type": "reference"},
            },
        )
    finally:
        app.dependency_overrides.pop(get_search_service, None)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["total"] == 1
    assert body["data"]["results"][0]["chunk_id"] == "chunk-1"
    assert dummy.calls == [("wing structure", "hybrid", 5, {"document_type": "reference"})]


@pytest.mark.unit
def test_trigger_ingestion_uses_blob_branch(client: TestClient) -> None:
    dummy = DummyIngestionService(blob_calls=[], sharepoint_calls=0, raw_calls=[])
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_ingestion_service] = lambda: dummy
    try:
        response = client.post(
            "/api/v1/ingest",
            json={"source": "blob", "document_ids": ["a.txt", "b.txt"]},
        )
    finally:
        app.dependency_overrides.pop(get_ingestion_service, None)

    assert response.status_code == 202
    body = response.json()
    assert body["success"] is True
    assert body["data"]["queued_count"] == 2
    assert dummy.blob_calls == [["a.txt", "b.txt"]]
    assert dummy.sharepoint_calls == 0


@pytest.mark.unit
def test_trigger_ingestion_uses_sharepoint_branch(client: TestClient) -> None:
    dummy = DummyIngestionService(blob_calls=[], sharepoint_calls=0, raw_calls=[])
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_ingestion_service] = lambda: dummy
    try:
        response = client.post("/api/v1/ingest", json={"source": "sharepoint"})
    finally:
        app.dependency_overrides.pop(get_ingestion_service, None)

    assert response.status_code == 202
    assert response.json()["data"]["queued_count"] == 3
    assert dummy.sharepoint_calls == 1


@pytest.mark.unit
def test_upload_and_ingest_reads_uploaded_file(client: TestClient) -> None:
    dummy = DummyIngestionService(blob_calls=[], sharepoint_calls=0, raw_calls=[])
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_ingestion_service] = lambda: dummy
    try:
        response = client.post(
            "/api/v1/ingest/upload",
            files={"file": ("spec.txt", b"hello world", "text/plain")},
        )
    finally:
        app.dependency_overrides.pop(get_ingestion_service, None)

    assert response.status_code == 202
    body = response.json()
    assert body["success"] is True
    assert body["data"]["queued_count"] == 1
    assert dummy.raw_calls == [(b"hello world", "spec.txt", "upload")]
