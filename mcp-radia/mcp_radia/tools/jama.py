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
    JamaChildrenResult,
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
            "Read the full content of ONE Jama Connect requirement that you can already "
            "identify, by its numeric item id. Returns the item's name, full description "
            "as plain text, workflow status, project, created/modified timestamps, a web "
            "URL, and any custom fields defined on the item type.\n"
            "\n"
            "Use when asked things like: 'show me Jama item 12345', 'what does that "
            "requirement actually say?', 'pull up the full text of item 12345'.\n"
            "\n"
            "Does NOT find items - you must already have the numeric id. To find an item "
            "from words, or from a document key like SRS-42, use jama_search first. Returns "
            "only this one item: it does not list the items nested under it (jama_get_children) "
            "or the items traced to it (list_related_items)."
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
            "FIND Jama Connect requirements when you do NOT yet know their id - search by "
            "words that appear in them, and/or filter by project or item type. Returns a "
            "page of matching item summaries (id, document key, name); use start_at to page "
            "through more.\n"
            "\n"
            "Use when asked things like: 'find the battery state-of-charge requirements', "
            "'what requirements mention thermal runaway?', 'list the safety requirements in "
            "project 7'. Also use this to turn a document key like SRS-42 into a numeric id.\n"
            "\n"
            "This is content search across MANY items. It does NOT follow links between "
            "items: a query naming one item returns items whose TEXT matches those words, "
            "not the items connected to it. For 'what is linked to / traced to / affected by "
            "X' use list_related_items; for 'what is inside / underneath X' use "
            "jama_get_children. Returns summaries only - call jama_get_item for full text."
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

    @server.tool(
        name="jama_get_children",
        title="Get Jama item children",
        description=(
            "List the items nested DIRECTLY INSIDE one Jama item in the document tree - "
            "its containment hierarchy. Given a folder, set or parent requirement, returns "
            "one page of the child items it contains (id, document key, name), plus the "
            "total child count.\n"
            "\n"
            "Use when asked things like: 'what's in folder 12345?', 'list the requirements "
            "under that set', 'show me the children of item 12345', 'what does this section "
            "break down into?'.\n"
            "\n"
            "This is CONTAINMENT ('what sits underneath this in the tree'), which is a "
            "different axis from TRACEABILITY ('what derives from / satisfies this') - for "
            "traceability use list_related_items instead. Returns only ONE level and ONE "
            "page: grandchildren are not included, so recurse by calling this again on a "
            "child's id. Does not search by text - use jama_search for that."
        ),
        annotations=READ_ONLY,
    )
    async def jama_get_children(
        item_id: Annotated[
            int, Field(description="Numeric Jama item id of the parent, e.g. 12345.", gt=0)
        ],
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
    ) -> JamaChildrenResult:
        return await guard(
            "jama_get_children",
            lambda: client.get_children(item_id, start_at=start_at, max_results=max_results),
        )

    names = ["jama_get_item", "jama_search", "jama_get_children"]
    logger.info("jama_tools_registered", tools=names, configured=client.is_configured)
    if not client.is_configured:
        # Registered but not usable: the tools stay visible so a client can
        # discover them, and each call fails with a message naming what to set.
        logger.warning("jama_not_configured", hint="set JAMA_BASE_URL and credentials")
    return names
