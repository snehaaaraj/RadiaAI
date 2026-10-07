"""MCP tools backed by the Jira Cloud connector.

Thin translation only: take MCP arguments, call the connector, convert
connector failures into ``ToolError``. All logic lives in
:mod:`mcp_radia.connectors.jira`.
"""

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from mcp_radia.connectors.jira import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    JiraClient,
    JiraIssue,
    JiraSearchResult,
)
from mcp_radia.logging import get_logger
from mcp_radia.tools._guard import READ_ONLY, guard

logger = get_logger(__name__)


def register_jira_tools(server: MCPServer, client: JiraClient) -> list[str]:
    """Register the Jira tools on ``server`` and return their names."""

    @server.tool(
        name="jira_get_issue",
        title="Get Jira issue",
        description=(
            "Fetch a single Jira issue by key (e.g. PROJ-123) or numeric id. Returns "
            "the summary, description as plain text, status, type, assignee, reporter, "
            "labels, parent, timestamps, a web URL, and the issue's links to other "
            "issues."
        ),
        annotations=READ_ONLY,
    )
    async def jira_get_issue(
        issue_key: Annotated[
            str,
            Field(description="Issue key such as PROJ-123, or the numeric issue id.", min_length=1),
        ],
    ) -> JiraIssue:
        return await guard("jira_get_issue", lambda: client.get_issue(issue_key))

    @server.tool(
        name="jira_search",
        title="Search Jira issues",
        description=(
            'Search Jira issues with JQL, e.g. \'project = PROJ AND status = "In Progress" '
            "ORDER BY updated DESC'. Returns a page of issue summaries. Jira's search API "
            "is token-paginated and reports no total count: to get the next page, pass the "
            "returned next_page_token back in. Call jira_get_issue for an issue's full "
            "description and links."
        ),
        annotations=READ_ONLY,
    )
    async def jira_search(
        jql: Annotated[
            str,
            Field(description="A JQL query string.", min_length=1),
        ],
        next_page_token: Annotated[
            str | None,
            Field(
                default=None, description="Token from a previous result, to fetch the next page."
            ),
        ] = None,
        max_results: Annotated[
            int,
            Field(
                default=DEFAULT_PAGE_SIZE,
                ge=1,
                le=MAX_PAGE_SIZE,
                description=f"Page size, 1-{MAX_PAGE_SIZE}.",
            ),
        ] = DEFAULT_PAGE_SIZE,
    ) -> JiraSearchResult:
        return await guard(
            "jira_search",
            lambda: client.search(
                jql=jql,
                next_page_token=next_page_token,
                max_results=max_results,
            ),
        )

    names = ["jira_get_issue", "jira_search"]
    logger.info("jira_tools_registered", tools=names, configured=client.is_configured)
    return names
