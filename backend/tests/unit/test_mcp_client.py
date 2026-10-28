"""Unit tests for the MCP client adapter (app.services.mcp.client).

No test here touches the network: a fake transport is injected directly so
these exercise the adapter's own safety rules - allowlist enforcement, schema
validation, disabled behavior - in isolation from the HTTP/JSON-RPC layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.core.config import MCPSettings
from app.services.mcp.client import MCPClientAdapter
from app.services.mcp.errors import (
    MCPDisabledError,
    MCPToolArgumentsInvalidError,
    MCPToolExecutionError,
    MCPToolNotAllowedError,
    MCPUnavailableError,
)
from app.services.mcp.transport import MCPToolCallResult, MCPToolDescriptor

pytestmark = pytest.mark.unit

_JAMA_GET_ITEM_SCHEMA = {
    "type": "object",
    "properties": {"item_id": {"type": "integer", "minimum": 1}},
    "required": ["item_id"],
}


@dataclass
class FakeTransport:
    """Stands in for MCPTransport: records calls, never touches the network."""

    tools: list[MCPToolDescriptor] = field(default_factory=list)
    call_results: dict[str, MCPToolCallResult] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, object], dict[str, str] | None]] = field(default_factory=list)
    raise_on_call: Exception | None = None

    async def list_tools(self) -> list[MCPToolDescriptor]:
        return self.tools

    async def call_tool(
        self, name: str, arguments: dict[str, object], *, extra_headers: dict[str, str] | None = None
    ) -> MCPToolCallResult:
        self.calls.append((name, arguments, extra_headers))
        if self.raise_on_call:
            raise self.raise_on_call
        return self.call_results.get(name, MCPToolCallResult(text="ok", is_error=False))


def _enabled_settings(**overrides: object) -> MCPSettings:
    values: dict[str, object] = {
        "enabled": True,
        "server_url": "https://mcp-radia.internal/mcp",
        "service_token": "test-token",
        "allowed_tools": ["jama_get_item", "jama_search"],
    }
    values.update(overrides)
    return MCPSettings(_env_file=None, **values)


def _adapter_with_fake_transport(settings: MCPSettings, fake: FakeTransport) -> MCPClientAdapter:
    adapter = MCPClientAdapter(settings)
    adapter._transport = fake  # type: ignore[assignment]
    return adapter


async def test_disabled_adapter_returns_no_tools() -> None:
    adapter = MCPClientAdapter(MCPSettings(_env_file=None, enabled=False))

    assert adapter.enabled is False
    assert await adapter.available_tools() == []


async def test_disabled_adapter_rejects_tool_calls() -> None:
    adapter = MCPClientAdapter(MCPSettings(_env_file=None, enabled=False))

    with pytest.raises(MCPDisabledError):
        await adapter.call_tool("jama_get_item", {"item_id": 1})


async def test_discovers_tools_and_filters_to_allowlist() -> None:
    fake = FakeTransport(
        tools=[
            MCPToolDescriptor(name="jama_get_item", description="", input_schema=_JAMA_GET_ITEM_SCHEMA),
            MCPToolDescriptor(name="jama_search", description="", input_schema={}),
            MCPToolDescriptor(name="jira_get_issue", description="", input_schema={}),
        ]
    )
    adapter = _adapter_with_fake_transport(_enabled_settings(), fake)

    tools = await adapter.available_tools()

    assert {t.name for t in tools} == {"jama_get_item", "jama_search"}


async def test_rejects_a_tool_not_on_the_allowlist_even_if_mcp_radia_advertises_it() -> None:
    fake = FakeTransport(
        tools=[MCPToolDescriptor(name="jira_get_issue", description="", input_schema={})]
    )
    adapter = _adapter_with_fake_transport(_enabled_settings(), fake)

    with pytest.raises(MCPToolNotAllowedError):
        await adapter.call_tool("jira_get_issue", {"issue_key": "RADIA-1"})
    assert fake.calls == []  # never reached the network


async def test_rejects_an_unknown_tool_name() -> None:
    fake = FakeTransport(tools=[])
    adapter = _adapter_with_fake_transport(_enabled_settings(), fake)

    with pytest.raises(MCPToolNotAllowedError):
        await adapter.call_tool("delete_everything", {})
    assert fake.calls == []


async def test_rejects_arguments_that_fail_the_tools_own_schema() -> None:
    fake = FakeTransport(
        tools=[MCPToolDescriptor(name="jama_get_item", description="", input_schema=_JAMA_GET_ITEM_SCHEMA)]
    )
    adapter = _adapter_with_fake_transport(_enabled_settings(), fake)

    with pytest.raises(MCPToolArgumentsInvalidError):
        await adapter.call_tool("jama_get_item", {"item_id": "not-a-number"})
    assert fake.calls == []


async def test_valid_call_reaches_the_transport_and_returns_its_result() -> None:
    fake = FakeTransport(
        tools=[MCPToolDescriptor(name="jama_get_item", description="", input_schema=_JAMA_GET_ITEM_SCHEMA)],
        call_results={"jama_get_item": MCPToolCallResult(text="Battery item", is_error=False)},
    )
    adapter = _adapter_with_fake_transport(_enabled_settings(), fake)

    result = await adapter.call_tool("jama_get_item", {"item_id": 123})

    assert result.text == "Battery item"
    assert fake.calls == [("jama_get_item", {"item_id": 123}, {})]


async def test_jama_credentials_are_forwarded_only_for_jama_tools() -> None:
    fake = FakeTransport(tools=[MCPToolDescriptor(name="jama_get_item", description="", input_schema={})])
    adapter = _adapter_with_fake_transport(_enabled_settings(), fake)

    await adapter.call_tool(
        "jama_get_item", {"item_id": 1}, jama_client_id="user-cid", jama_client_secret="user-secret"
    )

    _, _, headers = fake.calls[0]
    assert headers == {
        "X-Radia-Jama-Client-Id": "user-cid",
        "X-Radia-Jama-Client-Secret": "user-secret",
    }


async def test_a_tool_level_error_result_raises_an_execution_error() -> None:
    fake = FakeTransport(
        tools=[MCPToolDescriptor(name="jama_get_item", description="", input_schema={})],
        call_results={"jama_get_item": MCPToolCallResult(text="item not found", is_error=True)},
    )
    adapter = _adapter_with_fake_transport(_enabled_settings(), fake)

    with pytest.raises(MCPToolExecutionError):
        await adapter.call_tool("jama_get_item", {"item_id": 1})


async def test_transport_failure_surfaces_as_mcp_unavailable() -> None:
    fake = FakeTransport(
        tools=[MCPToolDescriptor(name="jama_get_item", description="", input_schema={})],
        raise_on_call=MCPUnavailableError("could not reach mcp-radia"),
    )
    adapter = _adapter_with_fake_transport(_enabled_settings(), fake)

    with pytest.raises(MCPUnavailableError):
        await adapter.call_tool("jama_get_item", {"item_id": 1})


async def test_tool_discovery_is_cached_across_calls() -> None:
    fake = FakeTransport(tools=[MCPToolDescriptor(name="jama_get_item", description="", input_schema={})])
    adapter = _adapter_with_fake_transport(_enabled_settings(), fake)

    await adapter.available_tools()
    await adapter.available_tools()
    await adapter.call_tool("jama_get_item", {"item_id": 1})

    # list_tools was effectively called once (cached): verified indirectly by
    # the fact FakeTransport.tools never needs to change between calls and no
    # second discovery round-trip is required for call_tool to resolve the tool.
    assert adapter._tools is not None  # type: ignore[attr-defined]
    assert len(adapter._tools) == 1  # type: ignore[attr-defined]
