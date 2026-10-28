"""Unit tests for the bounded MCP tool-calling loop (app.services.mcp.orchestrator)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import MCPSettings
from app.services.mcp.client import MCPClientAdapter
from app.services.mcp.orchestrator import run_chat_with_tools
from app.services.mcp.transport import MCPToolCallResult, MCPToolDescriptor

pytestmark = pytest.mark.unit

_JAMA_ITEM_SOURCE = {
    "document_key": "SRS-42",
    "web_url": "https://example.jamacloud.com/perspective.req#/items/1",
}


def _settings(**overrides: object) -> MCPSettings:
    values: dict[str, object] = {
        "enabled": True,
        "server_url": "https://mcp-radia.internal/mcp",
        "service_token": "tok",
        "allowed_tools": ["jama_get_item"],
        "max_tool_iterations": 3,
        "max_total_seconds": 5,
    }
    values.update(overrides)
    return MCPSettings(_env_file=None, **values)


def _tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments))
    )


def _message(
    *, content: str | None = None, tool_calls: list[SimpleNamespace] | None = None
) -> SimpleNamespace:
    return SimpleNamespace(content=content, tool_calls=tool_calls)


@dataclass
class FakeOpenAIClient:
    """Scripted sequence of assistant messages, one per ``chat_completion_with_tools`` call."""

    tool_turns: list[SimpleNamespace] = field(default_factory=list)
    final_answer: str = "Fallback answer."
    calls: int = 0

    def chat_completion_with_tools(
        self, messages, tools, *, model=None, max_tokens=None, temperature=None
    ):  # type: ignore[no-untyped-def]
        message = self.tool_turns[self.calls]
        self.calls += 1
        return message

    def chat_completion(self, messages, *, model=None, max_tokens=None, temperature=None) -> str:  # type: ignore[no-untyped-def]
        return self.final_answer


def _adapter_with_fake_transport(settings: MCPSettings, fake) -> MCPClientAdapter:  # type: ignore[no-untyped-def]
    adapter = MCPClientAdapter(settings)
    adapter._transport = fake  # type: ignore[assignment]
    return adapter


@dataclass
class FakeTransport:
    tools: list[MCPToolDescriptor]
    result: MCPToolCallResult

    async def list_tools(self) -> list[MCPToolDescriptor]:
        return self.tools

    async def call_tool(self, name, arguments, *, extra_headers=None) -> MCPToolCallResult:  # type: ignore[no-untyped-def]
        return self.result


async def test_falls_back_to_plain_completion_when_no_tools_are_available() -> None:
    settings = _settings(allowed_tools=[])
    fake_transport = FakeTransport(tools=[], result=MCPToolCallResult(text="", is_error=False))
    mcp_client = _adapter_with_fake_transport(settings, fake_transport)
    openai_client = FakeOpenAIClient(final_answer="Plain answer, no tools involved.")

    result = await run_chat_with_tools(
        openai_client=openai_client,  # type: ignore[arg-type]
        mcp_client=mcp_client,
        settings=settings,
        system_prompt="system",
        question="What is the sky?",
        conversation_history=[],
        model="gpt",
        max_tokens=100,
        trusted_source_hosts=frozenset(),
    )

    assert result.used_mcp is False
    assert result.answer == "Plain answer, no tools involved."


async def test_executes_an_approved_tool_call_and_surfaces_a_validated_source() -> None:
    settings = _settings()
    fake_transport = FakeTransport(
        tools=[MCPToolDescriptor(name="jama_get_item", description="", input_schema={})],
        result=MCPToolCallResult(
            text="Battery item text", is_error=False, structured_content=_JAMA_ITEM_SOURCE
        ),
    )
    mcp_client = _adapter_with_fake_transport(settings, fake_transport)
    openai_client = FakeOpenAIClient(
        tool_turns=[
            _message(tool_calls=[_tool_call("call-1", "jama_get_item", {"item_id": 1})]),
            _message(content="The battery item says X."),
        ]
    )

    result = await run_chat_with_tools(
        openai_client=openai_client,  # type: ignore[arg-type]
        mcp_client=mcp_client,
        settings=settings,
        system_prompt="system",
        question="What does SRS-42 say?",
        conversation_history=[],
        model="gpt",
        max_tokens=100,
        trusted_source_hosts=frozenset({"example.jamacloud.com"}),
    )

    assert result.used_mcp is True
    assert result.answer == "The battery item says X."
    assert len(result.sources) == 1
    assert result.sources[0].url == _JAMA_ITEM_SOURCE["web_url"]


async def test_source_url_on_an_untrusted_host_is_dropped() -> None:
    settings = _settings()
    fake_transport = FakeTransport(
        tools=[MCPToolDescriptor(name="jama_get_item", description="", input_schema={})],
        result=MCPToolCallResult(
            text="x", is_error=False, structured_content={"web_url": "https://evil.example/items/1"}
        ),
    )
    mcp_client = _adapter_with_fake_transport(settings, fake_transport)
    openai_client = FakeOpenAIClient(
        tool_turns=[
            _message(tool_calls=[_tool_call("call-1", "jama_get_item", {"item_id": 1})]),
            _message(content="answer"),
        ]
    )

    result = await run_chat_with_tools(
        openai_client=openai_client,  # type: ignore[arg-type]
        mcp_client=mcp_client,
        settings=settings,
        system_prompt="system",
        question="q",
        conversation_history=[],
        model="gpt",
        max_tokens=100,
        trusted_source_hosts=frozenset({"example.jamacloud.com"}),
    )

    assert result.sources == []


async def test_a_disallowed_tool_requested_by_the_model_is_never_executed() -> None:
    settings = _settings(allowed_tools=["jama_get_item"])
    fake_transport = FakeTransport(
        tools=[MCPToolDescriptor(name="jama_get_item", description="", input_schema={})],
        result=MCPToolCallResult(text="should not be reached", is_error=False),
    )
    mcp_client = _adapter_with_fake_transport(settings, fake_transport)
    # The model "hallucinates" a tool outside the allowlist; the adapter must
    # reject it before any network call, and the loop must still terminate.
    openai_client = FakeOpenAIClient(
        tool_turns=[
            _message(tool_calls=[_tool_call("call-1", "jira_delete_issue", {"issue_key": "X-1"})]),
            _message(content="I could not do that."),
        ]
    )

    result = await run_chat_with_tools(
        openai_client=openai_client,  # type: ignore[arg-type]
        mcp_client=mcp_client,
        settings=settings,
        system_prompt="system",
        question="q",
        conversation_history=[],
        model="gpt",
        max_tokens=100,
        trusted_source_hosts=frozenset(),
    )

    assert result.used_mcp is False
    assert result.answer == "I could not do that."


async def test_bounded_iteration_count_forces_a_final_answer() -> None:
    """The model keeps requesting tools forever; the loop must still terminate."""
    settings = _settings(max_tool_iterations=2)
    fake_transport = FakeTransport(
        tools=[MCPToolDescriptor(name="jama_get_item", description="", input_schema={})],
        result=MCPToolCallResult(text="item text", is_error=False),
    )
    mcp_client = _adapter_with_fake_transport(settings, fake_transport)
    # Every scripted turn keeps requesting a tool call - never stops on its own.
    openai_client = FakeOpenAIClient(
        tool_turns=[
            _message(tool_calls=[_tool_call(f"call-{i}", "jama_get_item", {"item_id": i})])
            for i in range(10)
        ],
        final_answer="Forced final answer after the iteration budget ran out.",
    )

    result = await run_chat_with_tools(
        openai_client=openai_client,  # type: ignore[arg-type]
        mcp_client=mcp_client,
        settings=settings,
        system_prompt="system",
        question="q",
        conversation_history=[],
        model="gpt",
        max_tokens=100,
        trusted_source_hosts=frozenset(),
    )

    assert openai_client.calls == settings.max_tool_iterations
    assert result.answer == "Forced final answer after the iteration budget ran out."
    assert result.used_mcp is True


async def test_malformed_tool_arguments_do_not_crash_the_loop() -> None:
    settings = _settings()
    fake_transport = FakeTransport(
        tools=[MCPToolDescriptor(name="jama_get_item", description="", input_schema={})],
        result=MCPToolCallResult(text="unused", is_error=False),
    )
    mcp_client = _adapter_with_fake_transport(settings, fake_transport)
    bad_call = SimpleNamespace(
        id="call-1", function=SimpleNamespace(name="jama_get_item", arguments="{not-json")
    )
    openai_client = FakeOpenAIClient(
        tool_turns=[_message(tool_calls=[bad_call]), _message(content="handled gracefully")]
    )

    result = await run_chat_with_tools(
        openai_client=openai_client,  # type: ignore[arg-type]
        mcp_client=mcp_client,
        settings=settings,
        system_prompt="system",
        question="q",
        conversation_history=[],
        model="gpt",
        max_tokens=100,
        trusted_source_hosts=frozenset(),
    )

    assert result.answer == "handled gracefully"
    assert result.used_mcp is False
