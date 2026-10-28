"""Server-side-enforced MCP client adapter for the chat integration.

This is the only thing in the backend allowed to talk to mcp-radia. It wraps
:class:`~app.services.mcp.transport.MCPTransport` with the safety rules the
chat orchestration layer depends on and must not reimplement itself:

  - tool discovery through the protocol (never a hard-coded tool list)
  - a server-side allowlist, enforced regardless of what the model requests
  - JSON-Schema validation of arguments before they ever reach mcp-radia
  - per-call size and time bounds
  - one shared, reused MCP session instead of one per tool call
  - every failure mode (disabled, unreachable, malformed, oversized, rejected)
    raised as a typed :mod:`app.services.mcp.errors` exception the caller can
    turn into a safe user-facing message
"""

from __future__ import annotations

import asyncio

import anyio
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError

from app.core.config import MCPSettings
from app.core.logging import get_logger
from app.services.mcp.errors import (
    MCPDisabledError,
    MCPToolArgumentsInvalidError,
    MCPToolExecutionError,
    MCPToolNotAllowedError,
    MCPUnavailableError,
)
from app.services.mcp.transport import MCPToolCallResult, MCPToolDescriptor, MCPTransport

logger = get_logger(__name__)

#: Headers carrying a signed-in user's linked Jama OAuth credentials, read by
#: mcp-radia's per-user credential passthrough (see mcp-radia/mcp_radia/tools/_identity.py).
#: Must match that module's header names exactly.
_JAMA_CLIENT_ID_HEADER = "X-Radia-Jama-Client-Id"
_JAMA_CLIENT_SECRET_HEADER = "X-Radia-Jama-Client-Secret"  # noqa: S105 (header name, not a secret)


class MCPClientAdapter:
    """Chat-facing façade over one mcp-radia server.

    One instance is created at application startup and shared across
    requests (see the DI container), so every chat request reuses the same
    MCP session rather than paying a fresh handshake each time.
    """

    def __init__(self, settings: MCPSettings) -> None:
        self._settings = settings
        self._transport: MCPTransport | None = None
        self._tools: dict[str, MCPToolDescriptor] | None = None
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return self._settings.is_configured

    def _require_enabled(self) -> MCPTransport:
        if not self.enabled:
            raise MCPDisabledError("MCP is disabled or not fully configured.")
        if self._transport is None:
            self._transport = MCPTransport(
                self._settings.server_url,
                service_token=self._settings.service_token,
                connect_timeout=self._settings.connect_timeout_seconds,
                read_timeout=self._settings.read_timeout_seconds,
                max_response_bytes=self._settings.max_response_bytes,
            )
        return self._transport

    async def aclose(self) -> None:
        if self._transport is not None:
            await self._transport.aclose()
            self._transport = None
        self._tools = None

    async def available_tools(self) -> list[MCPToolDescriptor]:
        """Return the approved subset of tools mcp-radia advertises.

        Discovers tools via ``tools/list`` (never a hard-coded list), then
        intersects with ``MCPSettings.allowed_tools`` - a tool mcp-radia adds
        tomorrow is invisible to chat until an operator explicitly allows it.
        Cached for the process lifetime; a server restart on this side clears it.
        """
        if not self.enabled:
            return []
        if self._tools is None:
            async with self._lock:
                if self._tools is None:
                    transport = self._require_enabled()
                    try:
                        with anyio.fail_after(self._settings.connect_timeout_seconds + 5):
                            discovered = await transport.list_tools()
                    except TimeoutError as exc:
                        raise MCPUnavailableError("Timed out discovering MCP tools.") from exc
                    self._tools = {t.name: t for t in discovered}
                    logger.info(
                        "mcp_tools_discovered",
                        discovered=sorted(self._tools),
                        allowed=sorted(self._settings.allowed_tools),
                    )
        allowed = set(self._settings.allowed_tools)
        return [tool for name, tool in self._tools.items() if name in allowed]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, object],
        *,
        jama_client_id: str | None = None,
        jama_client_secret: str | None = None,
    ) -> MCPToolCallResult:
        """Validate and execute one tool call, enforcing the allowlist and schema.

        Raises :class:`MCPToolNotAllowedError` for anything not on the
        allowlist - including a perfectly valid mcp-radia tool the operator
        has not approved - and :class:`MCPToolArgumentsInvalidError` when the
        arguments do not satisfy the tool's own declared JSON Schema. Neither
        reaches mcp-radia: both are rejected here, before the network call.
        """
        if not self.enabled:
            raise MCPDisabledError("MCP is disabled or not fully configured.")

        tools = {t.name: t for t in await self.available_tools()}
        descriptor = tools.get(name)
        if descriptor is None:
            logger.warning("mcp_tool_not_allowed", tool=name)
            raise MCPToolNotAllowedError(f"Tool '{name}' is not approved for chat use.")

        self._validate_arguments(descriptor, arguments)

        extra_headers: dict[str, str] = {}
        if name.startswith("jama_") and jama_client_id and jama_client_secret:
            extra_headers[_JAMA_CLIENT_ID_HEADER] = jama_client_id
            extra_headers[_JAMA_CLIENT_SECRET_HEADER] = jama_client_secret

        transport = self._require_enabled()
        try:
            with anyio.fail_after(self._settings.read_timeout_seconds + 2):
                result = await transport.call_tool(name, arguments, extra_headers=extra_headers)
        except TimeoutError as exc:
            raise MCPUnavailableError(f"Tool '{name}' timed out.") from exc

        if result.is_error:
            raise MCPToolExecutionError(result.text or f"Tool '{name}' failed.")
        return result

    @staticmethod
    def _validate_arguments(descriptor: MCPToolDescriptor, arguments: dict[str, object]) -> None:
        schema = descriptor.input_schema
        if not schema:
            return
        try:
            Draft202012Validator(schema).validate(arguments)
        except JSONSchemaValidationError as exc:
            raise MCPToolArgumentsInvalidError(
                f"Arguments for '{descriptor.name}' failed validation: {exc.message}"
            ) from exc
        except SchemaError:
            # mcp-radia's own schema is malformed - fail safe (reject the call)
            # rather than execute unvalidated arguments against a live system.
            logger.error("mcp_tool_schema_invalid", tool=descriptor.name)
            raise MCPToolArgumentsInvalidError(
                f"Tool '{descriptor.name}' has an invalid schema and cannot be called."
            ) from None
