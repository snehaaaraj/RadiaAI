"""Violet tools exercised through real in-memory MCP framing."""

from typing import Any

import anyio
import pytest

from mcp_radia.config import ServerSettings
from mcp_radia.connectors.errors import (
    ConnectorAuthError,
    ConnectorServiceError,
)
from mcp_radia.connectors.jama import JamaClient, JamaSettings
from mcp_radia.connectors.violet import VioletMCPClient, VioletSettings
from mcp_radia.server import build_server
from tests.conftest import connected_client

pytestmark = pytest.mark.unit


class FakeVioletTransport:
    """Records the remote call and optionally returns or raises a test outcome."""

    def __init__(
        self,
        *,
        result: dict[str, Any] | None = None,
        error: Exception | None = None,
        delay_forever: bool = False,
    ) -> None:
        self.result = result or {"programs": []}
        self.error = error
        self.delay_forever = delay_forever
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        if self.delay_forever:
            await anyio.sleep_forever()
        if self.error is not None:
            raise self.error
        return self.result


def _server(transport: FakeVioletTransport | None, *, api_key: str = "test-api-key"):
    settings = ServerSettings(_env_file=None, environment="test", log_level="DEBUG")
    jama = JamaClient(JamaSettings(_env_file=None, base_url=""))
    violet = VioletMCPClient(
        VioletSettings(_env_file=None, api_key=api_key, timeout_seconds=0.02),
        transport=transport,
    )
    return build_server(settings, jama_client=jama, violet_client=violet)


async def test_violet_tool_calls_remote_tool_and_returns_structured_result() -> None:
    fake = FakeVioletTransport(result={"programs": [{"id": "p-1", "name": "Flight"}]})

    async with connected_client(_server(fake)) as session:
        result = await session.call_tool("violet_list_programs", {})

    assert result.is_error is not True
    assert result.structured_content == {"programs": [{"id": "p-1", "name": "Flight"}]}
    assert fake.calls == [("listPrograms", {})]


async def test_violet_explore_tool_maps_arguments_to_remote_schema() -> None:
    fake = FakeVioletTransport()

    async with connected_client(_server(fake)) as session:
        result = await session.call_tool(
            "violet_explore_entities",
            {"filter_model": {"Part Number": {"filterType": "text"}}, "page": 2},
        )

    assert result.is_error is not True
    assert fake.calls == [
        (
            "exploreEntities",
            {
                "filterModel": {"Part Number": {"filterType": "text"}},
                "page": 2,
                "limit": 100,
                "includeParameters": False,
                "includeSubEntities": False,
                "includeSchemas": False,
                "isCountQuery": False,
            },
        )
    ]


async def test_violet_auth_failure_is_a_safe_mcp_tool_error() -> None:
    fake = FakeVioletTransport(
        error=ConnectorAuthError(
            "Violet rejected the API key or denied access.",
            system="violet",
            status_code=401,
        )
    )

    async with connected_client(_server(fake)) as session:
        result = await session.call_tool("violet_list_programs", {})

    assert result.is_error is True
    assert "Violet rejected the API key" in result.content[0].text


async def test_violet_timeout_is_a_safe_mcp_tool_error() -> None:
    fake = FakeVioletTransport(delay_forever=True)

    async with connected_client(_server(fake)) as session:
        result = await session.call_tool("violet_list_programs", {})

    assert result.is_error is True
    assert "Violet MCP timed out" in result.content[0].text


async def test_violet_unavailable_error_is_a_safe_mcp_tool_error() -> None:
    fake = FakeVioletTransport(
        error=ConnectorServiceError("Could not reach Violet MCP.", system="violet")
    )

    async with connected_client(_server(fake)) as session:
        result = await session.call_tool("violet_list_programs", {})

    assert result.is_error is True
    assert "Could not reach Violet MCP" in result.content[0].text


async def test_unconfigured_violet_tool_explains_which_setting_is_missing() -> None:
    async with connected_client(_server(None, api_key="")) as session:
        result = await session.call_tool("violet_list_programs", {})

    assert result.is_error is True
    assert "VIOLET_API_KEY" in result.content[0].text
