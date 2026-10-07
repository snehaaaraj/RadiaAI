"""MCP tools backed by the Confluence Cloud connector."""

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from mcp_radia.connectors.confluence import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    ConfluenceClient,
    ConfluencePage,
    ConfluenceSearchResult,
)
from mcp_radia.logging import get_logger
from mcp_radia.tools._guard import READ_ONLY, guard

logger = get_logger(__name__)


def register_confluence_tools(server: MCPServer, client: ConfluenceClient) -> list[str]:
    """Register the Confluence tools on ``server`` and return their names."""

    @server.tool(
        name="confluence_get_page",
        title="Get Confluence page",
        description=(
            "Fetch a single Confluence page by id, including its full body converted "
            "to plain text. Returns the title, space, status, version, and a web URL. "
            "Page ids come from confluence_search results."
        ),
        annotations=READ_ONLY,
    )
    async def confluence_get_page(
        page_id: Annotated[
            str,
            Field(description="Numeric Confluence page id, e.g. 123456789.", min_length=1),
        ],
    ) -> ConfluencePage:
        return await guard("confluence_get_page", lambda: client.get_page(page_id))

    @server.tool(
        name="confluence_search",
        title="Search Confluence",
        description=(
            "Search Confluence content. Give a free-text 'query' and optionally narrow "
            "by 'space_key' or 'content_type', or supply a raw 'cql' query for anything "
            "those cannot express. Returns a page of hits with excerpts; call "
            "confluence_get_page with a hit's id for the full body."
        ),
        annotations=READ_ONLY,
    )
    async def confluence_search(
        query: Annotated[
            str | None,
            Field(default=None, description="Free text to match against page content."),
        ] = None,
        space_key: Annotated[
            str | None,
            Field(default=None, description="Restrict to a space by key, e.g. ENG."),
        ] = None,
        content_type: Annotated[
            str | None,
            Field(default=None, description="Restrict to a content type, e.g. page or blogpost."),
        ] = None,
        cql: Annotated[
            str | None,
            Field(
                default=None,
                description=("Raw CQL. Overrides query/space_key/content_type when supplied."),
            ),
        ] = None,
        start: Annotated[
            int, Field(default=0, ge=0, description="Zero-based offset for paging.")
        ] = 0,
        limit: Annotated[
            int,
            Field(
                default=DEFAULT_PAGE_SIZE,
                ge=1,
                le=MAX_PAGE_SIZE,
                description=f"Page size, 1-{MAX_PAGE_SIZE}.",
            ),
        ] = DEFAULT_PAGE_SIZE,
    ) -> ConfluenceSearchResult:
        return await guard(
            "confluence_search",
            lambda: client.search(
                query=query,
                space_key=space_key,
                content_type=content_type,
                cql=cql,
                start=start,
                limit=limit,
            ),
        )

    names = ["confluence_get_page", "confluence_search"]
    logger.info("confluence_tools_registered", tools=names, configured=client.is_configured)
    return names
