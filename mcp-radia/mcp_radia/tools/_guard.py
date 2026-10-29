"""Shared error translation for the tool layer.

Connectors raise :class:`ConnectorError`; MCP clients understand ``ToolError``.
Every tool funnels through :func:`guard` so that translation happens in exactly
one place and no connector ever needs to import anything from MCP.
"""

from collections.abc import Awaitable, Callable

from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from mcp_radia.connectors.errors import ConnectorError
from mcp_radia.logging import get_logger

logger = get_logger(__name__)

#: Applied to every tool this server exposes. Nothing here writes.
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=True)


async def guard[T](operation: str, call: Callable[[], Awaitable[T]]) -> T:
    """Run a connector call, converting connector failures into MCP tool errors.

    ``ToolError`` messages are shown to the model, so they carry the
    remediation hint the connector produced (which variable is missing, no
    permission, rate-limited) rather than a generic failure. A ``ValueError``
    is an invalid argument (e.g. a Jama document key where a numeric id is
    required); its message tells the model how to retry, so it is passed on
    too instead of being masked as a generic "Error executing tool".
    """
    try:
        return await call()
    except ConnectorError as exc:
        logger.warning(
            "tool_call_failed",
            operation=operation,
            system=exc.system,
            error_type=type(exc).__name__,
            status_code=exc.status_code,
        )
        raise ToolError(str(exc)) from exc
    except ValueError as exc:
        logger.info("tool_call_invalid_argument", operation=operation)
        raise ToolError(str(exc)) from exc
