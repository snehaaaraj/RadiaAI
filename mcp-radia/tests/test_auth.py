"""Tests for the service-token bearer check on the Streamable HTTP transport."""

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_radia.auth import require_service_token


def _app() -> Starlette:
    async def ok(request):  # type: ignore[no-untyped-def]
        return PlainTextResponse("ok")

    return Starlette(routes=[Route("/mcp", ok)])


@pytest.mark.unit
def test_rejects_missing_token() -> None:
    app = require_service_token(_app(), token="secret-token")
    client = TestClient(app)

    response = client.get("/mcp")

    assert response.status_code == 401


@pytest.mark.unit
def test_rejects_wrong_token() -> None:
    app = require_service_token(_app(), token="secret-token")
    client = TestClient(app)

    response = client.get("/mcp", headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 401


@pytest.mark.unit
def test_accepts_correct_token() -> None:
    app = require_service_token(_app(), token="secret-token")
    client = TestClient(app)

    response = client.get("/mcp", headers={"Authorization": "Bearer secret-token"})

    assert response.status_code == 200
    assert response.text == "ok"


@pytest.mark.unit
def test_refuses_to_start_without_a_token() -> None:
    with pytest.raises(ValueError, match="MCP_RADIA_SERVICE_TOKEN"):
        require_service_token(_app(), token="")
