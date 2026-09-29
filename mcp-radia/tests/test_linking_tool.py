"""The linking MCP tool, exercised over a real MCP client session."""

import pytest

from mcp_radia.config import ServerSettings
from mcp_radia.server import build_server
from tests.conftest import connected_client
from tests.test_linking import _service

pytestmark = pytest.mark.unit


def _server():
    service, handlers = _service()
    server = build_server(
        ServerSettings(_env_file=None, environment="test"), linking_service=service
    )
    return server, handlers


async def test_the_linking_tool_is_advertised_and_read_only() -> None:
    server, _ = _server()

    async with connected_client(server) as session:
        tools = {t.name: t for t in (await session.list_tools()).tools}

    assert "list_related_items" in tools
    annotations = tools["list_related_items"].annotations
    assert annotations is not None
    assert annotations.read_only_hint is True


async def test_system_is_constrained_to_the_known_systems() -> None:
    """The schema should stop a bad system name before it reaches the service."""
    server, _ = _server()

    async with connected_client(server) as session:
        tools = {t.name: t for t in (await session.list_tools()).tools}

    schema = tools["list_related_items"].input_schema
    assert set(schema["required"]) == {"system", "item_id"}
    rendered = str(schema)
    for system in ("jama", "jira", "confluence", "genesys"):
        assert system in rendered


async def test_calling_it_returns_structured_related_items() -> None:
    server, _ = _server()

    async with connected_client(server) as session:
        result = await session.call_tool(
            "list_related_items", {"system": "jira", "item_id": "BMS-451"}
        )

    assert not result.is_error
    assert result.structured_content is not None
    keys = {item["key"] for item in result.structured_content["related"]}
    assert "BMS-452" in keys


async def test_an_unknown_system_is_rejected_by_the_schema() -> None:
    server, handlers = _server()

    async with connected_client(server) as session:
        result = await session.call_tool(
            "list_related_items", {"system": "sharepoint", "item_id": "1"}
        )

    assert result.is_error
    assert handlers["jira"].requests == []


async def test_a_bad_jama_id_surfaces_as_a_tool_error() -> None:
    server, _ = _server()

    async with connected_client(server) as session:
        result = await session.call_tool(
            "list_related_items", {"system": "jama", "item_id": "SRS-42"}
        )

    assert result.is_error
