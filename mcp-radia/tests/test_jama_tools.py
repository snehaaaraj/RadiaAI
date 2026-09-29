"""Tests for the Jama MCP tools, exercised through a real MCP client session.

These go through the full MCP path - tools/list and tools/call with real
JSON-RPC framing - so schema generation and error translation are covered, not
just the connector underneath.
"""

import pytest

from mcp_radia.config import ServerSettings
from mcp_radia.server import build_server
from tests.conftest import connected_client
from tests.jama_fixtures import (
    ITEM_PAYLOAD,
    SEARCH_PAYLOAD,
    basic_settings,
    json_responder,
    make_client,
)

pytestmark = pytest.mark.unit


def _server_with(responder, settings=None):  # type: ignore[no-untyped-def]
    """Build a server whose Jama connector is backed by a mock transport."""
    jama_client, handler = make_client(settings or basic_settings(), responder)
    server = build_server(
        ServerSettings(_env_file=None, environment="test"), jama_client=jama_client
    )
    return server, handler


async def test_both_jama_tools_are_advertised() -> None:
    server, _ = _server_with(json_responder(ITEM_PAYLOAD))

    async with connected_client(server) as session:
        tools = {t.name: t for t in (await session.list_tools()).tools}

    assert set(tools) == {"jama_get_item", "jama_search"}


async def test_tools_are_annotated_read_only() -> None:
    """The read-only guarantee has to be visible to the client, not just in a docstring."""
    server, _ = _server_with(json_responder(ITEM_PAYLOAD))

    async with connected_client(server) as session:
        tools = {t.name: t for t in (await session.list_tools()).tools}

    for tool in tools.values():
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False


async def test_get_item_schema_requires_item_id() -> None:
    server, _ = _server_with(json_responder(ITEM_PAYLOAD))

    async with connected_client(server) as session:
        tools = {t.name: t for t in (await session.list_tools()).tools}

    schema = tools["jama_get_item"].input_schema
    assert schema["required"] == ["item_id"]


async def test_search_schema_has_no_required_arguments() -> None:
    """An unfiltered search is legitimate; every argument is optional."""
    server, _ = _server_with(json_responder(SEARCH_PAYLOAD))

    async with connected_client(server) as session:
        tools = {t.name: t for t in (await session.list_tools()).tools}

    assert tools["jama_search"].input_schema.get("required", []) == []


async def test_calling_get_item_returns_structured_content() -> None:
    server, handler = _server_with(json_responder(ITEM_PAYLOAD))

    async with connected_client(server) as session:
        result = await session.call_tool("jama_get_item", {"item_id": 12345})

    assert not result.is_error
    assert result.structured_content is not None
    assert result.structured_content["document_key"] == "SRS-42"
    assert result.structured_content["status"] == "Approved"
    assert handler.last_request.url.path == "/rest/v1/items/12345"


async def test_calling_search_passes_arguments_through_to_jama() -> None:
    server, handler = _server_with(json_responder(SEARCH_PAYLOAD))

    async with connected_client(server) as session:
        result = await session.call_tool(
            "jama_search", {"query": "battery", "project_id": 7, "max_results": 10}
        )

    assert not result.is_error
    assert handler.last_request.url.params["contains"] == "battery"
    assert handler.last_request.url.params["project"] == "7"
    assert handler.last_request.url.params["maxResults"] == "10"


async def test_search_with_no_arguments_is_allowed() -> None:
    server, _ = _server_with(json_responder(SEARCH_PAYLOAD))

    async with connected_client(server) as session:
        result = await session.call_tool("jama_search", {})

    assert not result.is_error
    assert result.structured_content is not None
    assert result.structured_content["total"] == 137


async def test_a_missing_item_becomes_a_tool_error_not_a_crash() -> None:
    server, _ = _server_with(json_responder({"meta": {}}, status_code=404))

    async with connected_client(server) as session:
        result = await session.call_tool("jama_get_item", {"item_id": 999})

    assert result.is_error


async def test_unconfigured_jama_reports_what_to_set() -> None:
    """The failure has to tell the operator which variable is missing."""
    server, _ = _server_with(json_responder(ITEM_PAYLOAD), settings=basic_settings(base_url=""))

    async with connected_client(server) as session:
        result = await session.call_tool("jama_get_item", {"item_id": 1})

    assert result.is_error
    message = str(result.content)
    assert "JAMA_BASE_URL" in message


async def test_tools_are_still_listed_when_jama_is_unconfigured() -> None:
    """Discovery must not depend on credentials being present."""
    server, _ = _server_with(json_responder(ITEM_PAYLOAD), settings=basic_settings(base_url=""))

    async with connected_client(server) as session:
        tools = {t.name for t in (await session.list_tools()).tools}

    assert tools == {"jama_get_item", "jama_search"}


async def test_out_of_range_page_size_is_rejected_by_the_schema() -> None:
    """max_results above Jama's cap should fail validation, not silently clamp at the edge."""
    server, handler = _server_with(json_responder(SEARCH_PAYLOAD))

    async with connected_client(server) as session:
        result = await session.call_tool("jama_search", {"max_results": 500})

    assert result.is_error
    assert handler.requests == [], "invalid arguments must not reach Jama"
