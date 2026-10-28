"""Tests for bounded 429 backoff (mcp_radia.connectors.retry)."""

import httpx2
import pytest

from mcp_radia.connectors.retry import MAX_RETRY_ATTEMPTS, get_with_retry


@pytest.mark.unit
async def test_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("mcp_radia.connectors.retry.asyncio.sleep", fake_sleep)

    attempts = {"count": 0}

    def responder(request: httpx2.Request) -> httpx2.Response:
        attempts["count"] += 1
        if attempts["count"] < 2:
            return httpx2.Response(429, request=request)
        return httpx2.Response(200, json={"ok": True}, request=request)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(responder))
    response = await get_with_retry(client, "https://example.com/x", system="jama", operation="get")

    assert response.status_code == 200
    assert attempts["count"] == 2
    assert len(sleeps) == 1


@pytest.mark.unit
async def test_stops_after_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("mcp_radia.connectors.retry.asyncio.sleep", fake_sleep)

    attempts = {"count": 0}

    def responder(request: httpx2.Request) -> httpx2.Response:
        attempts["count"] += 1
        return httpx2.Response(429, request=request)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(responder))
    response = await get_with_retry(client, "https://example.com/x", system="jama", operation="get")

    assert response.status_code == 429
    assert attempts["count"] == MAX_RETRY_ATTEMPTS


@pytest.mark.unit
async def test_honors_retry_after_header(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("mcp_radia.connectors.retry.asyncio.sleep", fake_sleep)

    attempts = {"count": 0}

    def responder(request: httpx2.Request) -> httpx2.Response:
        attempts["count"] += 1
        if attempts["count"] < 2:
            return httpx2.Response(429, headers={"Retry-After": "2"}, request=request)
        return httpx2.Response(200, json={"ok": True}, request=request)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(responder))
    await get_with_retry(client, "https://example.com/x", system="jama", operation="get")

    assert sleeps == [2.0]


@pytest.mark.unit
async def test_does_not_retry_non_429_status() -> None:
    attempts = {"count": 0}

    def responder(request: httpx2.Request) -> httpx2.Response:
        attempts["count"] += 1
        return httpx2.Response(500, request=request)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(responder))
    response = await get_with_retry(client, "https://example.com/x", system="jama", operation="get")

    assert response.status_code == 500
    assert attempts["count"] == 1
