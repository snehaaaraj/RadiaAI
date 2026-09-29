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
            "Read ONE Jira issue - a ticket of work such as a bug, story or task - by its "
            "key (e.g. PROJ-123) or numeric id. Returns the summary, description as plain "
            "text, status, issue type, assignee, reporter, labels, parent, timestamps, a "
            "web URL, and its links to other issues.\n"
            "\n"
            "Use when asked things like: 'what's the status of PROJ-123?', 'who is working "
            "on PROJ-123?', 'show me that bug ticket'.\n"
            "\n"
            "Covers work items (bugs/stories/tasks) ONLY - not requirements (Jama) and not "
            "written documentation pages (Confluence). Requires a key you already have; to "
            "find issues from a description use jira_search. A key like PROJ-123 may also "
            "be a Jama document key, so if this reports the issue does not exist, try "
            "jama_search for the same key."
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
            "FIND Jira issues you cannot yet name, using a JQL query - filter by project, "
            "status, assignee, label, sprint, dates and so on. Example JQL: 'project = PROJ "
            'AND status = "In Progress" ORDER BY updated DESC\'. Returns a page of issue '
            "summaries.\n"
            "\n"
            "Use when asked things like: 'what bugs are open on the battery project?', "
            "'which tickets are assigned to Priya?', 'what was closed last sprint?'.\n"
            "\n"
            "Searches WORK TICKETS only - not requirements (jama_search) and not "
            "documentation pages (confluence_search). The 'jql' argument must be valid JQL, "
            "not plain English: translate the question into JQL first. Paging is by token, "
            "and no total count is returned - pass the returned next_page_token back in for "
            "the next page. Returns summaries only; call jira_get_issue for full detail."
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
