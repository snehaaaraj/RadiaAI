"""Unit tests for runtime config, auth helpers, search, and ingestion endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from app.core.config import (
    AppSettings,
    AzureBlobSettings,
    AzureOpenAISettings,
    AzureSearchSettings,
    get_settings,
)
from app.core.exceptions import AuthenticationNotConfiguredError
from app.core.security import Role, get_current_user
from app.dependencies.container import get_ingestion_job_store, get_search_service
from app.main import StartupConfigurationError, _resolve_settings

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


@pytest.mark.unit
@pytest.mark.parametrize(
    ("settings_type", "values"),
    [
        (
            AzureOpenAISettings,
            {
                "endpoint": "https://example.openai.azure.com",
                "api_key": "test-key",
                "chat_deployment": "gpt-4o-test",
                "embedding_deployment": "embedding-test",
            },
        ),
        (
            AzureOpenAISettings,
            {
                "endpoint": "https://test.openai.azure.com",
                "api_key": " ",
                "chat_deployment": "gpt-4o-test",
                "embedding_deployment": "embedding-test",
            },
        ),
        (
            AzureSearchSettings,
            {
                "endpoint": "https://example.search.windows.net",
                "api_key": "test-key",
            },
        ),
        (
            AzureBlobSettings,
            {
                "connection_string": (
                    "DefaultEndpointsProtocol=https;AccountName=example;AccountKey=example;"
                ),
            },
        ),
    ],
)
def test_azure_settings_reject_empty_or_placeholder_values(
    settings_type: type[AzureOpenAISettings | AzureSearchSettings | AzureBlobSettings],
    values: dict[str, str],
) -> None:
    with pytest.raises(ValueError):
        settings_type(**values)


@pytest.mark.unit
def test_resolve_settings_allows_fallback_in_explicit_test_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setattr(
        "app.main.get_settings", lambda: AppSettings(azure_openai={"endpoint": None})
    )

    settings = _resolve_settings()

    assert settings.environment == "test"
    assert str(settings.azure_openai.endpoint) == "https://example.openai.azure.com"


@pytest.mark.unit
def test_resolve_settings_fails_fast_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(
        "app.main.get_settings", lambda: AppSettings(azure_openai={"endpoint": None})
    )

    with pytest.raises(StartupConfigurationError, match="invalid for production") as exc_info:
        _resolve_settings()

    assert "azure_openai" in str(exc_info.value)


@pytest.mark.unit
def test_local_auth_bypass_returns_synthetic_user(test_settings: AppSettings) -> None:
    user = get_current_user(_make_request(), credentials=None, settings=test_settings)

    assert user.user_id == "local-dev-user"
    assert user.email == "dev@radia.local"
    assert user.auth_method == "local"
    assert user.has_role(Role.ADMIN) is True


@pytest.mark.unit
def test_unconfigured_auth_fails_closed_outside_local(test_settings: AppSettings) -> None:
    settings = test_settings.model_copy(update={"environment": "development"})

    with pytest.raises(AuthenticationNotConfiguredError):
        get_current_user(_make_request(), credentials=None, settings=settings)


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


class DummyIngestionJobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, object]] = {}
        self.requests: list[dict[str, object]] = []

    def enqueue(self, **kwargs):
        self.requests.append(kwargs)
        job = {
            "job_id": f"00000000-0000-0000-0000-{len(self.requests):012d}",
            "message": "Ingestion job queued.",
            "status": "queued",
            "source": kwargs["source"],
            "trigger": kwargs["trigger"],
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "attempt": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "failure_details": [],
        }
        self.jobs[job["job_id"]] = job
        return job, True

    def get(self, job_id: str):
        from app.ingestion.job_store import JobNotFoundError

        if job_id not in self.jobs:
            raise JobNotFoundError(job_id)
        return self.jobs[job_id]


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
    dummy = DummyIngestionJobStore()
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_ingestion_job_store] = lambda: dummy
    try:
        response = client.post(
            "/api/v1/ingest",
            json={"source": "blob", "document_ids": ["a.txt", "b.txt"]},
        )
    finally:
        app.dependency_overrides.pop(get_ingestion_job_store, None)

    assert response.status_code == 202
    body = response.json()
    assert body["success"] is True
    assert body["data"]["queued_count"] == 1
    assert dummy.requests[0]["source"] == "blob"
    assert dummy.requests[0]["document_ids"] == ["a.txt", "b.txt"]


@pytest.mark.unit
def test_trigger_ingestion_uses_sharepoint_branch(client: TestClient) -> None:
    dummy = DummyIngestionJobStore()
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_ingestion_job_store] = lambda: dummy
    try:
        response = client.post("/api/v1/ingest", json={"source": "sharepoint"})
    finally:
        app.dependency_overrides.pop(get_ingestion_job_store, None)

    assert response.status_code == 202
    assert response.json()["data"]["queued_count"] == 1
    assert dummy.requests[0]["source"] == "sharepoint"


@pytest.mark.unit
def test_upload_and_ingest_reads_uploaded_file(client: TestClient) -> None:
    dummy = DummyIngestionJobStore()
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_ingestion_job_store] = lambda: dummy
    try:
        response = client.post(
            "/api/v1/ingest/upload",
            files={"file": ("spec.txt", b"hello world", "text/plain")},
        )
    finally:
        app.dependency_overrides.pop(get_ingestion_job_store, None)

    assert response.status_code == 202
    body = response.json()
    assert body["success"] is True
    assert body["data"]["queued_count"] == 1
    assert dummy.requests[0]["upload"] == (b"hello world", "spec.txt", "text/plain")


@pytest.mark.unit
def test_ingestion_rejects_unsupported_source(client: TestClient) -> None:
    response = client.post("/api/v1/ingest", json={"source": "external"})
    assert response.status_code == 422


@pytest.mark.unit
def test_ingestion_job_status_is_retrievable(client: TestClient) -> None:
    dummy = DummyIngestionJobStore()
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_ingestion_job_store] = lambda: dummy
    try:
        queued = client.post("/api/v1/ingest", json={"source": "blob"})
        job_id = queued.json()["data"]["job_id"]
        status_response = client.get(f"/api/v1/ingest/jobs/{job_id}")
    finally:
        app.dependency_overrides.pop(get_ingestion_job_store, None)

    assert status_response.status_code == 200
    assert status_response.json()["data"]["status"] == "queued"
