"""
Unit tests for the liveness (`/health/live`) and readiness (`/health/ready`,
legacy `/health`) endpoints.

`test_app` (see conftest.py) is session-scoped and its FastAPI lifespan never
runs in tests, so `app.state.openai_client` / `search_service` are normally
unset - this is what previously let the stub health endpoint report "OK" for
everything. These tests both prove the previous false-positive behavior is
gone and exercise the real degraded/down/caching/timeout/leak-prevention
paths using lightweight probe doubles installed directly on `app.state`.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, cast

import pytest
from fastapi import FastAPI

import app.api.v1.endpoints.health as health_module
from app.schemas.health import DependencyHealth, HealthResponse, ServiceStatus

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

_MISSING = object()
_TRACKED_STATE_ATTRS = (
    "health_readiness_cache",
    "health_probe_runner",
    "openai_client",
    "search_service",
    "sharepoint_client",
    "jama_client",
)


@pytest.fixture(autouse=True)
def _isolate_health_state(client: TestClient) -> Any:
    """Snapshot/restore health-related app.state attributes around each test.

    `test_app` is shared across the whole session, so anything a test sets on
    `app.state` here (probe doubles, cache, override runner) must not leak
    into unrelated tests.
    """
    app = cast(FastAPI, client.app)
    original = {attr: getattr(app.state, attr, _MISSING) for attr in _TRACKED_STATE_ATTRS}
    yield
    for attr, value in original.items():
        if value is _MISSING:
            if hasattr(app.state, attr):
                delattr(app.state, attr)
        else:
            setattr(app.state, attr, value)


def _install_runner(client: TestClient, response: HealthResponse) -> None:
    """Force the readiness endpoint to return a fixed HealthResponse, bypassing real probes."""

    async def _runner(_settings: object) -> HealthResponse:
        return response

    cast(FastAPI, client.app).state.health_probe_runner = _runner


def _dep(name: str, status: ServiceStatus, **kwargs: Any) -> DependencyHealth:
    return DependencyHealth(name=name, status=status, **kwargs)


# --- Liveness ------------------------------------------------------------------


@pytest.mark.unit
def test_liveness_returns_200_and_ok_status(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "ok"
    assert "version" in body
    assert "environment" in body
    # Liveness must never report (or imply probing) dependency state.
    assert "dependencies" not in body


@pytest.mark.unit
def test_liveness_includes_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert "X-Request-ID" in response.headers


# --- Readiness: healthy ---------------------------------------------------------


@pytest.mark.unit
def test_readiness_returns_200_when_all_dependencies_reachable(client: TestClient) -> None:
    _install_runner(
        client,
        HealthResponse(
            status=ServiceStatus.OK,
            version="0.1.0",
            environment="local",
            dependencies=[
                _dep("azure_openai", ServiceStatus.OK, latency_ms=12.0, message="Reachable"),
                _dep("azure_search", ServiceStatus.OK, latency_ms=8.0, message="Reachable"),
                _dep("blob_storage", ServiceStatus.OK, latency_ms=5.0, message="Reachable"),
                _dep("sharepoint", ServiceStatus.NOT_CONFIGURED, message="Not configured"),
                _dep("jama", ServiceStatus.NOT_CONFIGURED, message="Not configured"),
            ],
        ),
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "ok"
    names = {dep["name"] for dep in body["dependencies"]}
    assert names == {"azure_openai", "azure_search", "blob_storage", "sharepoint", "jama"}


@pytest.mark.unit
def test_legacy_health_path_aliases_readiness(client: TestClient) -> None:
    _install_runner(
        client,
        HealthResponse(
            status=ServiceStatus.OK, version="0.1.0", environment="local", dependencies=[]
        ),
    )

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


# --- Readiness: degraded and down ------------------------------------------------


@pytest.mark.unit
def test_readiness_returns_503_when_a_required_dependency_is_down(client: TestClient) -> None:
    _install_runner(
        client,
        HealthResponse(
            status=ServiceStatus.DOWN,
            version="0.1.0",
            environment="local",
            dependencies=[
                _dep("azure_openai", ServiceStatus.DOWN, message="Service unreachable"),
                _dep("azure_search", ServiceStatus.OK, message="Reachable"),
                _dep("blob_storage", ServiceStatus.OK, message="Reachable"),
            ],
        ),
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["data"]["status"] == "down"


@pytest.mark.unit
def test_readiness_returns_200_degraded_when_only_an_optional_dependency_is_down(
    client: TestClient,
) -> None:
    """An unreachable optional-but-configured dependency degrades, but must not fail readiness."""
    _install_runner(
        client,
        HealthResponse(
            status=ServiceStatus.DEGRADED,
            version="0.1.0",
            environment="local",
            dependencies=[
                _dep("azure_openai", ServiceStatus.OK, message="Reachable"),
                _dep("azure_search", ServiceStatus.OK, message="Reachable"),
                _dep("blob_storage", ServiceStatus.OK, message="Reachable"),
                _dep("sharepoint", ServiceStatus.DOWN, message="Service unreachable"),
            ],
        ),
    )

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "degraded"


# --- Real probe wiring, no override runner ---------------------------------------


@pytest.mark.unit
def test_readiness_reports_down_when_required_clients_are_not_wired(client: TestClient) -> None:
    """Without an override runner, unwired required clients report DOWN (503) rather

    than the old stub's hardcoded OK - this is the false positive being fixed.
    Configured-but-unconfigured optional integrations report NOT_CONFIGURED
    distinctly, and never affect the overall degraded/down status.
    """
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()["data"]
    assert body["status"] == "down"
    by_name = {dep["name"]: dep for dep in body["dependencies"]}
    assert by_name["azure_openai"]["status"] == "down"
    assert by_name["azure_openai"]["message"] == "Client unavailable"
    assert by_name["azure_search"]["status"] == "down"
    # The autouse blob stub (InMemoryBlobClient) reports healthy.
    assert by_name["blob_storage"]["status"] == "ok"
    assert by_name["sharepoint"]["status"] == "not_configured"
    assert by_name["jama"]["status"] == "not_configured"


@pytest.mark.unit
def test_readiness_never_leaks_provider_error_details(client: TestClient) -> None:
    """A probe failure must surface only a generic message, never the raw exception text."""

    class _LeakyProbe:
        def probe(self) -> None:
            raise RuntimeError("secret-connection-string=AccountKey=TOP-SECRET")

    cast(FastAPI, client.app).state.openai_client = _LeakyProbe()

    response = client.get("/api/v1/health/ready")

    assert "TOP-SECRET" not in response.text
    assert "secret-connection-string" not in response.text
    by_name = {dep["name"]: dep for dep in response.json()["data"]["dependencies"]}
    assert by_name["azure_openai"]["status"] == "down"
    assert by_name["azure_openai"]["message"] == "Service unreachable"


@pytest.mark.unit
def test_readiness_probe_times_out_without_hanging(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A slow dependency must not block the readiness response past the bounded timeout."""
    monkeypatch.setattr(health_module, "_PROBE_TIMEOUT_SECONDS", 0.05)

    class _SlowProbe:
        def probe(self) -> None:
            time.sleep(1.0)

    cast(FastAPI, client.app).state.openai_client = _SlowProbe()

    started = time.monotonic()
    response = client.get("/api/v1/health/ready")
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    by_name = {dep["name"]: dep for dep in response.json()["data"]["dependencies"]}
    assert by_name["azure_openai"]["status"] == "down"
    assert by_name["azure_openai"]["message"] == "Probe timed out"


# --- Caching ----------------------------------------------------------------------


@pytest.mark.unit
def test_readiness_result_is_cached_between_calls(client: TestClient) -> None:
    """Repeated polling within the TTL must not re-probe every dependency."""

    class _CountingProbe:
        def __init__(self) -> None:
            self.call_count = 0

        def probe(self) -> None:
            self.call_count += 1

    app = cast(FastAPI, client.app)
    counting_probe = _CountingProbe()
    app.state.openai_client = counting_probe
    app.state.search_service = counting_probe

    client.get("/api/v1/health/ready")
    client.get("/api/v1/health/ready")
    client.get("/api/v1/health/ready")

    # The same probe backs both azure_openai and azure_search, so a single
    # cache-miss build calls it twice; the cached hits below must not add more.
    assert counting_probe.call_count == 2


@pytest.mark.unit
def test_readiness_cache_expires_after_ttl(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(health_module, "_CACHE_TTL_SECONDS", 0.05)

    class _CountingProbe:
        def __init__(self) -> None:
            self.call_count = 0

        def probe(self) -> None:
            self.call_count += 1

    app = cast(FastAPI, client.app)
    counting_probe = _CountingProbe()
    app.state.openai_client = counting_probe
    app.state.search_service = counting_probe

    client.get("/api/v1/health/ready")
    time.sleep(0.1)
    client.get("/api/v1/health/ready")

    # Two builds (before/after TTL expiry) x two dependencies sharing the probe.
    assert counting_probe.call_count == 4


# --- Request ID plumbing -----------------------------------------------------------


@pytest.mark.unit
def test_readiness_includes_request_id(client: TestClient) -> None:
    _install_runner(
        client,
        HealthResponse(
            status=ServiceStatus.OK, version="0.1.0", environment="local", dependencies=[]
        ),
    )
    response = client.get("/api/v1/health/ready")
    assert "X-Request-ID" in response.headers


@pytest.mark.unit
def test_readiness_echoes_provided_request_id(client: TestClient) -> None:
    _install_runner(
        client,
        HealthResponse(
            status=ServiceStatus.OK, version="0.1.0", environment="local", dependencies=[]
        ),
    )
    custom_id = "test-request-id-12345"
    response = client.get("/api/v1/health/ready", headers={"X-Request-ID": custom_id})
    assert response.headers["X-Request-ID"] == custom_id
