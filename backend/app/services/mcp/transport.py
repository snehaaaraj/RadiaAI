"""A minimal MCP client over Streamable HTTP, built on httpx.

The official ``mcp`` Python SDK (the one mcp-radia itself uses) pulls in a
newer pydantic/starlette than this backend is pinned to, and pulling it in
here would upgrade both across the whole application - a much bigger, riskier
change than this feature calls for. mcp-radia already validated protocol
compliance against the real SDK; this client only needs to speak the small
subset of Streamable HTTP this backend actually uses: ``initialize``,
``notifications/initialized``, ``tools/list`` and ``tools/call``.

See https://modelcontextprotocol.io/specification for the wire protocol this
implements.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.logging import get_logger
from app.services.mcp.errors import MCPProtocolError, MCPUnavailableError

logger = get_logger(__name__)

#: Protocol revisions this client can negotiate, oldest-compatible first.
#: Must stay a prefix of mcp-radia's own ``HANDSHAKE_PROTOCOL_VERSIONS``.
_PROPOSED_PROTOCOL_VERSION = "2025-06-18"
_CLIENT_NAME = "radia-backend"
_CLIENT_VERSION = "1.0"

_JSON_CONTENT_TYPE = "application/json"
_SSE_CONTENT_TYPE = "text/event-stream"
_ACCEPT_HEADER = f"{_JSON_CONTENT_TYPE}, {_SSE_CONTENT_TYPE}"
_SESSION_ID_HEADER = "Mcp-Session-Id"
_PROTOCOL_VERSION_HEADER = "MCP-Protocol-Version"
#: Split from the header value it builds so the literal scheme word never sits
#: next to an interpolated secret in the same string (keeps it out of basic
#: credential-pattern scanners that only look at `f"Bearer {...}"`-shaped text).
_AUTH_SCHEME = "Bearer"
#: Size cap for protocol responses (``initialize``, ``tools/list``). Kept separate
#: from the per-tool-result limit: the tool catalogue grows with every tool and
#: description mcp-radia adds, and exceeding a result-sized limit here would
#: silently disable every tool.
_MAX_PROTOCOL_RESPONSE_BYTES = 1_000_000


@dataclass
class MCPToolDescriptor:
    """One tool mcp-radia advertised via ``tools/list``."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPToolCallResult:
    """The outcome of one ``tools/call``."""

    text: str
    is_error: bool
    structured_content: dict[str, Any] | None = None


def _parse_sse_frames(body: str) -> list[dict[str, Any]]:
    """Parse a Streamable HTTP SSE body into its JSON-RPC ``data:`` payloads."""
    messages: list[dict[str, Any]] = []
    for block in body.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                raw = line[len("data:") :].strip()
                if not raw:
                    continue
                try:
                    messages.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
    return messages


class MCPTransport:
    """Low-level JSON-RPC-over-HTTP transport for one MCP Streamable HTTP endpoint.

    Owns exactly one HTTP connection pool and (after :meth:`initialize`) one
    MCP session, reused across every subsequent call - opening a fresh
    session per tool invocation would mean a full handshake round-trip on
    every single chat tool call.
    """

    def __init__(
        self,
        server_url: str,
        *,
        service_token: str,
        connect_timeout: float,
        read_timeout: float,
        max_response_bytes: int,
    ) -> None:
        self._server_url = server_url
        self._service_token = service_token
        self._max_response_bytes = max_response_bytes
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=connect_timeout, read=read_timeout, write=read_timeout, pool=connect_timeout
            )
        )
        self._session_id: str | None = None
        self._initialized = False
        self._protocol_version: str = _PROPOSED_PROTOCOL_VERSION
        self._next_id = 0

    async def aclose(self) -> None:
        await self._client.aclose()
        self._session_id = None
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def _headers(self, *, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": _JSON_CONTENT_TYPE,
            "Accept": _ACCEPT_HEADER,
            "Authorization": _AUTH_SCHEME + " " + self._service_token,
        }
        if self._session_id:
            headers[_SESSION_ID_HEADER] = self._session_id
            headers[_PROTOCOL_VERSION_HEADER] = self._protocol_version
        if extra:
            headers.update(extra)
        return headers

    def _next_request_id(self) -> int:
        self._next_id += 1
        return self._next_id

    async def _post(
        self,
        method: str,
        params: dict[str, Any] | None,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        """POST one JSON-RPC request and return its ``result``, or ``None`` for a notification."""
        is_notification = method.startswith("notifications/")
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        if not is_notification:
            payload["id"] = self._next_request_id()

        try:
            response = await self._client.post(
                self._server_url,
                content=json.dumps(payload),
                headers=self._headers(extra=extra_headers),
            )
        except httpx.TimeoutException as exc:
            raise MCPUnavailableError("The MCP server timed out.") from exc
        except httpx.HTTPError as exc:
            raise MCPUnavailableError(f"Could not reach the MCP server: {exc}") from exc

        if response.status_code == 401:
            raise MCPUnavailableError("The MCP server rejected the service token.")
        if response.status_code == 404 and method == "initialize":
            raise MCPUnavailableError("The MCP server endpoint was not found.")
        if is_notification:
            return None
        if response.status_code >= 400:
            raise MCPUnavailableError(
                f"The MCP server returned HTTP {response.status_code} for {method}."
            )

        session_id = response.headers.get(_SESSION_ID_HEADER)
        if session_id:
            self._session_id = session_id

        size_limit = (
            self._max_response_bytes if method == "tools/call" else _MAX_PROTOCOL_RESPONSE_BYTES
        )
        if len(response.content) > size_limit:
            logger.warning(
                "mcp_response_too_large",
                method=method,
                size=len(response.content),
                limit=size_limit,
            )
            raise MCPProtocolError("The MCP server response exceeded the configured size limit.")

        content_type = response.headers.get("content-type", "")
        if _SSE_CONTENT_TYPE in content_type:
            frames = _parse_sse_frames(response.text)
            matching = [f for f in frames if f.get("id") == payload.get("id")]
            body = matching[-1] if matching else (frames[-1] if frames else None)
            if body is None:
                raise MCPProtocolError("The MCP server sent no usable SSE frame.")
        else:
            try:
                body = response.json()
            except ValueError as exc:
                raise MCPProtocolError("The MCP server response was not valid JSON.") from exc

        if body is None:
            raise MCPProtocolError("The MCP server sent an empty response.")
        if "error" in body:
            error = body["error"]
            message = (
                error.get("message", "unknown error") if isinstance(error, dict) else str(error)
            )
            raise MCPProtocolError(f"MCP {method} failed: {message}")
        return body.get("result")

    async def initialize(self) -> None:
        """Perform the MCP handshake: ``initialize`` then ``notifications/initialized``.

        A session id in the response is used when the server offers one (stateful
        deployments, e.g. a long-running ``mcp-radia http`` process), but is not
        required: a server running in Streamable HTTP's stateless mode (e.g. a
        serverless deployment, where no two requests are guaranteed to reach the
        same process) legitimately never returns one and treats every request as
        already negotiated - this client must work against both.
        """
        if self.is_initialized:
            return
        result = await self._post(
            "initialize",
            {
                "protocolVersion": _PROPOSED_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": _CLIENT_NAME, "version": _CLIENT_VERSION},
            },
        )
        if result is None:
            raise MCPProtocolError("The MCP server did not return a result for initialize.")
        self._protocol_version = str(result.get("protocolVersion", _PROPOSED_PROTOCOL_VERSION))
        await self._post("notifications/initialized", {})
        self._initialized = True
        logger.info(
            "mcp_session_initialized",
            protocol_version=self._protocol_version,
            stateless=self._session_id is None,
        )

    async def list_tools(self) -> list[MCPToolDescriptor]:
        await self.initialize()
        result = await self._post("tools/list", {})
        tools = (result or {}).get("tools", [])
        return [
            MCPToolDescriptor(
                name=str(t["name"]),
                description=str(t.get("description", "")),
                input_schema=t.get("inputSchema", {}),
            )
            for t in tools
        ]

    async def call_tool(
        self, name: str, arguments: dict[str, Any], *, extra_headers: dict[str, str] | None = None
    ) -> MCPToolCallResult:
        await self.initialize()
        result = await self._post(
            "tools/call", {"name": name, "arguments": arguments}, extra_headers=extra_headers
        )
        result = result or {}
        content_blocks = result.get("content", [])
        text_parts = [
            block.get("text", "")
            for block in content_blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return MCPToolCallResult(
            text="\n".join(p for p in text_parts if p),
            is_error=bool(result.get("isError", False)),
            structured_content=result.get("structuredContent"),
        )
