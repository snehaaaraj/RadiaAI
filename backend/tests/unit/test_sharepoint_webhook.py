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


class StubSharePointClient:
    """Minimal stand-in for SharePointStandardsClient used by the webhook service."""

    def __init__(self) -> None:
        self.resolve_calls = 0

    def auth_headers(self) -> dict[str, str]:
        return {"Authorization": "Bearer test-token"}

    def resolve_folder_context(self) -> tuple[str, str]:
        self.resolve_calls += 1
        return "drive-1", "folder-item-1"


class StubJobStore:
    """Records durable queue submissions without touching Azure."""

    def __init__(self) -> None:
        self.jobs: list[dict[str, Any]] = []

    def enqueue(self, **kwargs: Any) -> tuple[dict[str, Any], bool]:
        self.jobs.append(kwargs)
        return {"job_id": "job-1"}, True


def _valid_notification() -> dict[str, str]:
    return {
        "clientState": "correct-secret",
        "subscriptionId": "sub-existing",
        "resource": "/drives/drive-1/root",
    }


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
        job_store=StubJobStore(),
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
        job_store=StubJobStore(),
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
        job_store=StubJobStore(),
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
        job_store=StubJobStore(),
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
                "resource": "/drives/drive-1/root",
                "notification_url": "https://myapp.vercel.app/api/v1/ingest/webhook",
            }
        ).encode("utf-8"),
    )
    job_store = StubJobStore()

    service = SharePointWebhookService(
        settings=settings,
        sharepoint_client=StubSharePointClient(),
        blob_client=blob_client,
        job_store=job_store,
    )

    triggered = service.handle_notification([_valid_notification()])

    assert triggered is True
    assert job_store.jobs[0]["source"] == "sharepoint"
    assert job_store.jobs[0]["trigger"] == "webhook"


@pytest.mark.unit
def test_handle_notification_queues_durable_ingestion_job() -> None:
    settings = _configured_settings()
    blob_client = InMemoryBlobClient()
    blob_client.upload_blob(
        "system/sharepoint-webhook-subscription.json",
        json.dumps(
            {
                "subscription_id": "sub-existing",
                "expiration": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
                "client_state": "correct-secret",
                "resource": "/drives/drive-1/root",
                "notification_url": "https://myapp.vercel.app/api/v1/ingest/webhook",
            }
        ).encode("utf-8"),
    )
    job_store = StubJobStore()

    service = SharePointWebhookService(
        settings=settings,
        sharepoint_client=StubSharePointClient(),
        blob_client=blob_client,
        job_store=job_store,
    )

    assert service.handle_notification([_valid_notification()]) is True
    assert len(job_store.jobs) == 1


@pytest.mark.unit
def test_handle_notification_rejects_batch_with_mismatched_subscription() -> None:
    blob_client = InMemoryBlobClient()
    blob_client.upload_blob(
        "system/sharepoint-webhook-subscription.json",
        json.dumps(
            {
                "subscription_id": "sub-existing",
                "expiration": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
                "client_state": "correct-secret",
                "resource": "/drives/drive-1/root",
            }
        ).encode("utf-8"),
    )
    job_store = StubJobStore()
    service = SharePointWebhookService(
        settings=_configured_settings(),
        sharepoint_client=StubSharePointClient(),
        blob_client=blob_client,
        job_store=job_store,
    )
    invalid_notification = _valid_notification()
    invalid_notification["subscriptionId"] = "another-subscription"

    assert service.handle_notification([_valid_notification(), invalid_notification]) is False
    assert job_store.jobs == []


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
                "resource": "/drives/drive-1/root",
                "notification_url": "https://myapp.vercel.app/api/v1/ingest/webhook",
            }
        ).encode("utf-8"),
    )
    job_store = StubJobStore()

    service = SharePointWebhookService(
        settings=settings,
        sharepoint_client=StubSharePointClient(),
        blob_client=blob_client,
        job_store=job_store,
    )

    notification = _valid_notification()
    notification["clientState"] = "wrong-secret"
    triggered = service.handle_notification([notification])

    assert triggered is False
    assert job_store.jobs == []


@pytest.mark.unit
def test_handle_notification_without_existing_subscription_state() -> None:
    settings = _configured_settings()
    job_store = StubJobStore()

    service = SharePointWebhookService(
        settings=settings,
        sharepoint_client=StubSharePointClient(),
        blob_client=InMemoryBlobClient(),
        job_store=job_store,
    )

    triggered = service.handle_notification([_valid_notification()])

    assert triggered is False
    assert job_store.jobs == []
