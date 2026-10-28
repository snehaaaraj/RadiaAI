"""Tests for the stateless Streamable HTTP ASGI app (mcp_radia.asgi), used by the
Vercel serverless deployment.

Exercises the exact gap that bit the Vercel deployment during development: the
MCP SDK auto-restricts the allowed ``Host`` header to loopback values whenever
``host`` is ``127.0.0.1``/``localhost``/``::1`` (``MCP_RADIA_HOST``'s own
default) - correct for ``cli.py``'s own local HTTP listener, but fatal for a
public deployment, where the real inbound ``Host`` is the deployment's own
domain and would otherwise be rejected with HTTP 421 on every request.
"""

import pytest
from starlette.testclient import TestClient

from mcp_radia.asgi import build_http_app
from mcp_radia.config import ServerSettings

pytestmark = pytest.mark.unit

_HEADERS = {"Authorization": "Bearer test-token"}


def _stateless_app(**overrides: object):  # type: ignore[no-untyped-def]
    settings = ServerSettings(
        _env_file=None, service_token="test-token", http_path="/mcp", **overrides
    )
    return build_http_app(settings, stateless=True)


def test_accepts_requests_from_a_public_deployment_host() -> None:
    """The Host header is the deployment's own domain, not loopback - must not 421."""
    app = _stateless_app()
    with TestClient(app, base_url="https://mcp-radia-demo.vercel.app") as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
            headers={**_HEADERS, "Accept": "application/json, text/event-stream"},
        )

    assert response.status_code == 200
    # Stateless mode never hands out a session id - every request is self-contained.
    assert "Mcp-Session-Id" not in response.headers


def test_tools_list_works_without_a_prior_initialize_call() -> None:
    """Stateless mode is 'born-ready': no cross-request session memory is needed or used."""
    app = _stateless_app()
    with TestClient(app, base_url="https://mcp-radia-demo.vercel.app") as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={**_HEADERS, "Accept": "application/json, text/event-stream"},
        )

    assert response.status_code == 200
    assert "jama_get_item" in response.text


def test_still_rejects_requests_without_the_service_token() -> None:
    app = _stateless_app()
    with TestClient(app, base_url="https://mcp-radia-demo.vercel.app") as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={"Accept": "application/json, text/event-stream"},
        )

    assert response.status_code == 401
