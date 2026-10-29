"""Unit tests for the MCP Streamable HTTP transport's response size limits.

The HTTP layer is replaced with ``httpx.MockTransport``; nothing touches the network.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.services.mcp.errors import MCPProtocolError
from app.services.mcp.transport import MCPTransport

pytestmark = pytest.mark.unit

_RESULT_LIMIT = 32_000


def _transport(handler) -> MCPTransport:  # type: ignore[no-untyped-def]
    transport = MCPTransport(
        "https://mcp-radia.internal/mcp",
        service_token="test-token",
        connect_timeout=5,
        read_timeout=5,
        max_response_bytes=_RESULT_LIMIT,
    )
    transport._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return transport


def _respond(request: httpx.Request, result: dict) -> httpx.Response:
    payload = json.loads(request.content)
    if "id" not in payload:
        return httpx.Response(202)
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"], "result": result})


async def test_a_tool_catalogue_larger_than_the_result_limit_is_still_discovered() -> None:
    """Regression: a 33 KB tools/list once tripped the 32 KB result limit and hid every tool."""
    tools = [
        {
            "name": f"tool_{i}",
            "description": "x" * 4_000,
            "inputSchema": {"type": "object", "properties": {}},
        }
        for i in range(12)
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        method = json.loads(request.content)["method"]
        if method == "initialize":
            return _respond(request, {"protocolVersion": "2025-06-18"})
        return _respond(request, {"tools": tools})

    transport = _transport(handler)

    discovered = await transport.list_tools()

    assert len(discovered) == 12
    await transport.aclose()


async def test_an_oversized_tool_result_is_still_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        method = json.loads(request.content)["method"]
        if method == "initialize":
            return _respond(request, {"protocolVersion": "2025-06-18"})
        return _respond(request, {"content": [{"type": "text", "text": "y" * (_RESULT_LIMIT + 1)}]})

    transport = _transport(handler)

    with pytest.raises(MCPProtocolError, match="size limit"):
        await transport.call_tool("jama_get_item", {"item_id": 1})
    await transport.aclose()
