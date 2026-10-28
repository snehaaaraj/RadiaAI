"""Bounded tool-calling loop that augments chat generation with MCP tools.

Standard OpenAI-style function calling: the model is offered only the
approved MCP tool schemas (:meth:`MCPClientAdapter.available_tools`), may
request zero or more of them, and each request is executed through the
adapter - which re-enforces the allowlist and schema validation regardless of
what the model asked for. The loop is bounded on two axes so a model that
keeps requesting tools cannot run forever: a maximum number of sequential
tool-calling round-trips (``MCPSettings.max_tool_iterations``) and a wall-clock
deadline for the whole turn (``MCPSettings.max_total_seconds``).

Tool results are appended to the conversation as untrusted data (regular
``tool`` role messages), never reinterpreted as instructions - the system
prompt passed in must already tell the model to treat them that way (see
``app.prompts.chat_prompts``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import anyio
from anyio import to_thread

from app.core.logging import get_logger
from app.services.mcp.client import MCPClientAdapter
from app.services.mcp.errors import MCPError
from app.services.mcp.transport import MCPToolDescriptor

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageToolCall

    from app.core.azure_clients import OpenAIClient
    from app.core.config import MCPSettings

logger = get_logger(__name__)

#: Upper bound on how much of one tool result's text is fed back to the model,
#: independent of the transport-level response-size cap - keeps a single large
#: result from dominating the context window of a multi-tool-call turn.
_MAX_TOOL_RESULT_CHARS = 6000


@dataclass
class ToolSource:
    """A source link surfaced by a tool call, for the chat UI's citation chip."""

    label: str
    url: str


@dataclass
class ToolAugmentedAnswer:
    """Result of running the bounded tool-calling loop."""

    answer: str
    used_mcp: bool
    sources: list[ToolSource] = field(default_factory=list)


def _to_openai_tool(descriptor: MCPToolDescriptor) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": descriptor.name,
            "description": descriptor.description[:1024],
            "parameters": descriptor.input_schema or {"type": "object", "properties": {}},
        },
    }


def _validate_source_url(url: str, *, trusted_hosts: frozenset[str]) -> bool:
    """Only let a tool-supplied URL through if it is plain https on a known host.

    Tool results are untrusted data, so a URL embedded in one is never
    rendered as-is: only an exact-host https link is accepted, which rules
    out ``javascript:`` URIs, open redirects to another host, and anything
    else a compromised or buggy upstream might return.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme == "https" and parsed.hostname is not None and parsed.hostname in trusted_hosts


def _extract_source(name: str, structured: dict[str, Any] | None, *, trusted_hosts: frozenset[str]) -> ToolSource | None:
    if not structured:
        return None
    url = structured.get("web_url")
    if not isinstance(url, str) or not _validate_source_url(url, trusted_hosts=trusted_hosts):
        return None
    label = structured.get("document_key") or structured.get("name") or name
    return ToolSource(label=str(label), url=url)


async def run_chat_with_tools(
    *,
    openai_client: OpenAIClient,
    mcp_client: MCPClientAdapter,
    settings: MCPSettings,
    system_prompt: str,
    question: str,
    conversation_history: list[dict[str, str]],
    model: str,
    max_tokens: int | None,
    trusted_source_hosts: frozenset[str],
    jama_client_id: str | None = None,
    jama_client_secret: str | None = None,
) -> ToolAugmentedAnswer:
    """Run the bounded tool-augmented chat loop and return the final answer.

    Falls back to a plain (tool-less) completion if MCP has no approved
    tools available right now - the caller does not need to branch on that.
    """
    tools = await mcp_client.available_tools()
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": question})

    if not tools:
        answer = await to_thread.run_sync(
            lambda: openai_client.chat_completion(messages, model=model, max_tokens=max_tokens)
        )
        return ToolAugmentedAnswer(answer=answer, used_mcp=False)

    tool_schemas = [_to_openai_tool(t) for t in tools]
    used_mcp = False
    sources: dict[str, ToolSource] = {}

    try:
        with anyio.fail_after(settings.max_total_seconds):
            for iteration in range(settings.max_tool_iterations):
                message = await to_thread.run_sync(
                    lambda: openai_client.chat_completion_with_tools(
                        messages, tool_schemas, model=model, max_tokens=max_tokens
                    )
                )
                tool_calls = getattr(message, "tool_calls", None) or []
                if not tool_calls:
                    return ToolAugmentedAnswer(
                        answer=message.content or "", used_mcp=used_mcp, sources=list(sources.values())
                    )

                messages.append(
                    {
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": call.id,
                                "type": "function",
                                "function": {
                                    "name": call.function.name,
                                    "arguments": call.function.arguments,
                                },
                            }
                            for call in tool_calls
                        ],
                    }
                )

                for call in tool_calls:
                    result_text, source, success = await _execute_one_tool_call(
                        call,
                        mcp_client=mcp_client,
                        trusted_source_hosts=trusted_source_hosts,
                        jama_client_id=jama_client_id,
                        jama_client_secret=jama_client_secret,
                    )
                    if success:
                        used_mcp = True
                    if source is not None:
                        sources[source.url] = source
                    messages.append(
                        {"role": "tool", "tool_call_id": call.id, "content": result_text}
                    )

                logger.info("mcp_tool_iteration_complete", iteration=iteration + 1, tool_count=len(tool_calls))

            # Iteration budget exhausted: ask once more, with tools withdrawn, so the
            # model must answer from what it already has instead of looping forever.
            final_answer = await to_thread.run_sync(
                lambda: openai_client.chat_completion(messages, model=model, max_tokens=max_tokens)
            )
            return ToolAugmentedAnswer(answer=final_answer, used_mcp=used_mcp, sources=list(sources.values()))
    except TimeoutError:
        logger.warning("mcp_tool_loop_deadline_exceeded", max_total_seconds=settings.max_total_seconds)
        return ToolAugmentedAnswer(
            answer=(
                "I was retrieving live engineering data for this but it took too long. "
                "Please try again, or ask a narrower question."
            ),
            used_mcp=used_mcp,
            sources=list(sources.values()),
        )


async def _execute_one_tool_call(
    call: ChatCompletionMessageToolCall,
    *,
    mcp_client: MCPClientAdapter,
    trusted_source_hosts: frozenset[str],
    jama_client_id: str | None,
    jama_client_secret: str | None,
) -> tuple[str, ToolSource | None, bool]:
    """Execute one model-requested tool call, never letting a failure escape as an exception.

    A disallowed tool, invalid arguments, or an upstream failure all become a
    short, safe ``tool`` message the model sees as data - never a stack trace,
    an internal hostname, or a secret. Returns ``(message, source, success)``.
    """
    name = call.function.name
    try:
        arguments = json.loads(call.function.arguments or "{}")
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be a JSON object")
    except (json.JSONDecodeError, ValueError):
        logger.info("mcp_tool_call_malformed_arguments", tool=name)
        return "error: the arguments for this tool call were malformed", None, False

    try:
        result = await mcp_client.call_tool(
            name, arguments, jama_client_id=jama_client_id, jama_client_secret=jama_client_secret
        )
    except MCPError as exc:
        logger.info("mcp_tool_call_failed", tool=name, error_type=type(exc).__name__)
        return f"error: {exc}", None, False

    source = _extract_source(name, result.structured_content, trusted_hosts=trusted_source_hosts)
    text = result.text or (json.dumps(result.structured_content) if result.structured_content else "")
    return text[:_MAX_TOOL_RESULT_CHARS], source, True
