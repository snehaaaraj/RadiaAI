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
            "Read ONE Confluence page - written documentation such as a design document, "
            "meeting notes, a runbook or a spec write-up - by its page id. Returns the "
            "full body converted to plain text, plus title, space, status, version and a "
            "web URL.\n"
            "\n"
            "Use when asked things like: 'open the architecture design doc', 'what do the "
            "notes from that review say?', 'show me page 123456789'.\n"
            "\n"
            "Needs a numeric page id, which normally comes from confluence_search - a page "
            "TITLE will not work here, so search first. Only works for hits whose type is "
            "'page': confluence_search also returns blog posts, databases and other content "
            "types, and passing one of those ids here fails with 'not found'. Pass "
            "content_type='page' to confluence_search to avoid that. Covers prose "
            "documentation only, not requirements (Jama) and not work tickets (Jira)."
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
            "FIND Confluence documentation pages by their content - design docs, meeting "
            "notes, runbooks, how-to guides, specs written as prose. Give free-text "
            "'query', optionally narrowed by 'space_key' or 'content_type'; supply raw "
            "'cql' only for filters those cannot express. Returns a page of hits with "
            "excerpts.\n"
            "\n"
            "Use when asked things like: 'is there a design doc for the charging module?', "
            "'find the onboarding runbook', 'what did we write up about the thermal test?'.\n"
            "\n"
            "Pass 'query' as a few plain keywords - 'engineering leadership meeting' - not a "
            "whole sentence, and do NOT put quotation marks inside it: quotes are escaped "
            "into the search literal and will match nothing. Dates are often formatted in "
            "the title rather than the body, so search the topic words and pick the right "
            "date from the results instead of putting the date in the query.\n"
            "\n"
            "Searches WRITTEN DOCUMENTATION only. It does not search requirements "
            "(jama_search) or work tickets (jira_search) - if a question is about what the "
            "product must do, prefer jama_search; if it is about work status, prefer "
            "jira_search. Results include blog posts and databases as well as pages, so set "
            "content_type='page' when the next step is to open a hit with "
            "confluence_get_page. Returns excerpts, not full pages: call "
            "confluence_get_page with a hit's id for the whole body."
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
