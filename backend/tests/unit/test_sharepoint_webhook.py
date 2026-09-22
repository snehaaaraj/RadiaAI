"""Unit tests for the SharePoint change-notification webhook service."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from tests.conftest import InMemoryBlobClient

from app.core.config import SharePointSettings
from app.ingestion.sharepoint_webhook import SharePointWebhookService
from app.ingestion.status_store import IngestionStatusStore


class StubSharePointClient:
    """Minimal stand-in for SharePointStandardsClient used by the webhook service."""

    def __init__(self) -> None:
        self.resolve_calls = 0

    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": "Bearer test-token"}

    def resolve_folder_context(self) -> tuple[str, str]:
        self.resolve_calls += 1
        return "drive-1", "folder-item-1"


class StubIngestionService:
    """Records calls to ingest_from_sharepoint without touching Azure."""

    def __init__(self) -> None:
        self.calls = 0

    def ingest_from_sharepoint(self) -> dict[str, Any]:
        self.calls += 1
        return {"processed": 1, "skipped": 0, "failed": 0, "details": []}


def _configured_settings(**overrides: Any) -> SharePointSettings:
    defaults: dict[str, Any] = {
        "tenant_id": "tenant",
        "client_id": "client",
        "client_secret": "secret",
        "site_url": "https://example.sharepoint.com/sites/demo",
        "webhook_enabled": True,
        "webhook_public_base_url": "https://myapp.vercel.app",
    }
    defaults.update(overrides)
    return SharePointSettings(**defaults)


_RealHttpxClient = httpx.Client


def _mock_graph_client(monkeypatch: pytest.MonkeyPatch, handler: Any) -> None:
    """Patch httpx.Client used inside the webhook module to a MockTransport-backed client."""
    import app.ingestion.sharepoint_webhook as module

    def _factory(*_args: Any, **_kwargs: Any) -> httpx.Client:
        return _RealHttpxClient(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(module.httpx, "Client", _factory)


@pytest.mark.unit
def test_ensure_subscription_noop_when_webhook_not_configured() -> None:
    settings = _configured_settings(webhook_enabled=False)
    service = SharePointWebhookService(
        settings=settings,
        sharepoint_client=StubSharePointClient(),
        blob_client=InMemoryBlobClient(),
        ingestion_service=StubIngestionService(),
    )

    service.ensure_subscription()

    assert service._load_state() is None


@pytest.mark.unit
def test_ensure_subscription_creates_and_persists_state(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _configured_settings()
    sharepoint_client = StubSharePointClient()
    blob_client = InMemoryBlobClient()
    expiration = (datetime.now(UTC) + timedelta(days=3)).isoformat()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body["resource"] == "/drives/drive-1/root"
        assert body["notificationUrl"] == "https://myapp.vercel.app/api/v1/ingest/webhook"
        return httpx.Response(
            201,
            json={
                "id": "sub-123",
                "expirationDateTime": expiration,
            },
        )

    _mock_graph_client(monkeypatch, handler)

    service = SharePointWebhookService(
        settings=settings,
        sharepoint_client=sharepoint_client,
        blob_client=blob_client,
        ingestion_service=StubIngestionService(),
    )
    service.ensure_subscription()

    state = service._load_state()
    assert state is not None
    assert state["subscription_id"] == "sub-123"
    assert sharepoint_client.resolve_calls == 1


@pytest.mark.unit
def test_ensure_subscription_skips_when_far_from_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _configured_settings()
    blob_client = InMemoryBlobClient()
    blob_client.upload_blob(
        "system/sharepoint-webhook-subscription.json",
        json.dumps(
            {
                "subscription_id": "sub-existing",
                "expiration": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
                "client_state": "secret-state",
                "resource": "/drives/drive-1/items/folder-item-1",
                "notification_url": "https://myapp.vercel.app/api/v1/ingest/webhook",
            }
        ).encode("utf-8"),
    )

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - should not run
        raise AssertionError("Graph API should not be called when subscription is still fresh")

    _mock_graph_client(monkeypatch, handler)

    service = SharePointWebhookService(
        settings=settings,
        sharepoint_client=StubSharePointClient(),
        blob_client=blob_client,
        ingestion_service=StubIngestionService(),
    )
    service.ensure_subscription()

    state = service._load_state()
    assert state is not None
    assert state["subscription_id"] == "sub-existing"


@pytest.mark.unit
def test_ensure_subscription_renews_when_close_to_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _configured_settings()
    blob_client = InMemoryBlobClient()
    new_expiration = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    blob_client.upload_blob(
        "system/sharepoint-webhook-subscription.json",
        json.dumps(
            {
                "subscription_id": "sub-existing",
                "expiration": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "client_state": "secret-state",
                "resource": "/drives/drive-1/items/folder-item-1",
                "notification_url": "https://myapp.vercel.app/api/v1/ingest/webhook",
            }
        ).encode("utf-8"),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url.path.endswith("/sub-existing")
        return httpx.Response(
            200, json={"id": "sub-existing", "expirationDateTime": new_expiration}
        )

    _mock_graph_client(monkeypatch, handler)

    service = SharePointWebhookService(
        settings=settings,
        sharepoint_client=StubSharePointClient(),
        blob_client=blob_client,
        ingestion_service=StubIngestionService(),
    )
    service.ensure_subscription()

    state = service._load_state()
    assert state is not None
    assert state["expiration"] == new_expiration


@pytest.mark.unit
def test_handle_notification_triggers_ingestion_on_valid_client_state() -> None:
    settings = _configured_settings()
    blob_client = InMemoryBlobClient()
    blob_client.upload_blob(
        "system/sharepoint-webhook-subscription.json",
        json.dumps(
            {
                "subscription_id": "sub-existing",
                "expiration": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
                "client_state": "correct-secret",
                "resource": "/drives/drive-1/items/folder-item-1",
                "notification_url": "https://myapp.vercel.app/api/v1/ingest/webhook",
            }
        ).encode("utf-8"),
    )
    ingestion_service = StubIngestionService()

    service = SharePointWebhookService(
        settings=settings,
        sharepoint_client=StubSharePointClient(),
        blob_client=blob_client,
        ingestion_service=ingestion_service,
    )

    triggered = service.handle_notification([{"clientState": "correct-secret"}])

    assert triggered is True
    assert ingestion_service.calls == 1


@pytest.mark.unit
def test_handle_notification_records_ingestion_status() -> None:
    settings = _configured_settings()
    blob_client = InMemoryBlobClient()
    blob_client.upload_blob(
        "system/sharepoint-webhook-subscription.json",
        json.dumps(
            {
                "subscription_id": "sub-existing",
                "expiration": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
                "client_state": "correct-secret",
                "resource": "/drives/drive-1/items/folder-item-1",
                "notification_url": "https://myapp.vercel.app/api/v1/ingest/webhook",
            }
        ).encode("utf-8"),
    )
    status_store = IngestionStatusStore(blob_client)

    service = SharePointWebhookService(
        settings=settings,
        sharepoint_client=StubSharePointClient(),
        blob_client=blob_client,
        ingestion_service=StubIngestionService(),
        status_store=status_store,
    )

    service.handle_notification([{"clientState": "correct-secret"}])

    latest = status_store.get_latest()
    assert latest is not None
    assert latest["trigger"] == "webhook"
    assert latest["outcome"] == "success"
    assert latest["processed"] == 1


@pytest.mark.unit
def test_handle_notification_rejects_invalid_client_state() -> None:
    settings = _configured_settings()
    blob_client = InMemoryBlobClient()
    blob_client.upload_blob(
        "system/sharepoint-webhook-subscription.json",
        json.dumps(
            {
                "subscription_id": "sub-existing",
                "expiration": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
                "client_state": "correct-secret",
                "resource": "/drives/drive-1/items/folder-item-1",
                "notification_url": "https://myapp.vercel.app/api/v1/ingest/webhook",
            }
        ).encode("utf-8"),
    )
    ingestion_service = StubIngestionService()

    service = SharePointWebhookService(
        settings=settings,
        sharepoint_client=StubSharePointClient(),
        blob_client=blob_client,
        ingestion_service=ingestion_service,
    )

    triggered = service.handle_notification([{"clientState": "wrong-secret"}])

    assert triggered is False
    assert ingestion_service.calls == 0


@pytest.mark.unit
def test_handle_notification_without_existing_subscription_state() -> None:
    settings = _configured_settings()
    ingestion_service = StubIngestionService()

    service = SharePointWebhookService(
        settings=settings,
        sharepoint_client=StubSharePointClient(),
        blob_client=InMemoryBlobClient(),
        ingestion_service=ingestion_service,
    )

    triggered = service.handle_notification([{"clientState": "anything"}])

    assert triggered is False
    assert ingestion_service.calls == 0
