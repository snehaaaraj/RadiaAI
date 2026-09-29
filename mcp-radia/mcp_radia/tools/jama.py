"""MCP tools backed by the Jama connector.

Thin translation only: take MCP arguments, call the connector, convert
connector failures into ``ToolError`` via the shared guard. All logic lives in
:mod:`mcp_radia.connectors.jama`.
"""

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from mcp_radia.connectors.jama import (
    MAX_PAGE_SIZE,
    JamaClient,
    JamaItem,
    JamaSearchResult,
)
from mcp_radia.logging import get_logger
from mcp_radia.tools._guard import READ_ONLY, guard

logger = get_logger(__name__)


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
        return await guard("jama_get_item", lambda: client.get_item(item_id))

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
        return await guard(
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
