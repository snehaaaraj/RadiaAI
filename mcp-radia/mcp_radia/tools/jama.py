"""MCP tools backed by the Jama connector.

The tool functions are a thin translation layer only: they take MCP arguments,
call the connector, and convert :class:`ConnectorError` into ``ToolError`` so
the client gets an actionable message instead of a stack trace. All business
logic lives in :mod:`mcp_radia.connectors.jama`.

Both tools are read-only and annotated as such.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_radia.connectors.errors import ConnectorError
from mcp_radia.connectors.jama import (
    MAX_PAGE_SIZE,
    JamaClient,
    JamaItem,
    JamaSearchResult,
)
from mcp_radia.logging import get_logger

logger = get_logger(__name__)

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=True)


async def _guard[T](operation: str, call: Callable[[], Awaitable[T]]) -> T:
    """Run a connector call, converting connector failures into MCP tool errors.

    ``ToolError`` messages are shown to the model, so they carry the remediation
    hint the connector produced (missing credentials, no permission, ...) rather
    than a generic failure.
    """
    try:
        return await call()
    except ConnectorError as exc:
        logger.warning(
            "jama_tool_failed",
            operation=operation,
            error_type=type(exc).__name__,
            status_code=exc.status_code,
        )
        raise ToolError(str(exc)) from exc


def register_jama_tools(server: MCPServer, client: JamaClient) -> list[str]:
    """Register the Jama tools on ``server`` and return their names."""

    @server.tool(
        name="jama_get_item",
        title="Get Jama item",
        description=(
            "Fetch a single Jama Connect item by its numeric id. Returns the item's "
            "name, description (as plain text), status, project, timestamps, a web "
            "URL, and the full raw field map including custom fields."
        ),
        annotations=READ_ONLY,
    )
    async def jama_get_item(
        item_id: Annotated[int, Field(description="Numeric Jama item id, e.g. 12345.", gt=0)],
    ) -> JamaItem:
        return await _guard("jama_get_item", lambda: client.get_item(item_id))

    @server.tool(
        name="jama_search",
        title="Search Jama items",
        description=(
            "Search Jama Connect items by free text and/or filter by project and item "
            "type. Returns a page of summaries; use start_at to page through results. "
            "Call jama_get_item for the full content of any result."
        ),
        annotations=READ_ONLY,
    )
    async def jama_search(
        query: Annotated[
            str | None,
            Field(default=None, description="Free-text to match against item content."),
        ] = None,
        project_id: Annotated[
            int | None, Field(default=None, description="Restrict to this Jama project id.")
        ] = None,
        item_type_id: Annotated[
            int | None, Field(default=None, description="Restrict to this Jama item type id.")
        ] = None,
        start_at: Annotated[
            int, Field(default=0, ge=0, description="Zero-based offset for paging.")
        ] = 0,
        max_results: Annotated[
            int,
            Field(
                default=MAX_PAGE_SIZE,
                ge=1,
                le=MAX_PAGE_SIZE,
                description=f"Page size, 1-{MAX_PAGE_SIZE}.",
            ),
        ] = MAX_PAGE_SIZE,
    ) -> JamaSearchResult:
        return await _guard(
            "jama_search",
            lambda: client.search(
                query=query,
                project_id=project_id,
                item_type_id=item_type_id,
                start_at=start_at,
                max_results=max_results,
            ),
        )

    names = ["jama_get_item", "jama_search"]
    logger.info("jama_tools_registered", tools=names, configured=client.is_configured)
    if not client.is_configured:
        # Registered but not usable: the tools stay visible so a client can
        # discover them, and each call fails with a message naming what to set.
        logger.warning("jama_not_configured", hint="set JAMA_BASE_URL and credentials")
    return names
