"""The cross-system linking MCP tool."""

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from mcp_radia.linking.models import LinkableSystem, RelatedItemsResult
from mcp_radia.linking.service import LinkingService
from mcp_radia.logging import get_logger
from mcp_radia.tools._guard import READ_ONLY, guard

logger = get_logger(__name__)


def register_linking_tools(server: MCPServer, service: LinkingService) -> list[str]:
    """Register the linking tool on ``server`` and return its name."""

    @server.tool(
        name="list_related_items",
        title="List related items across systems",
        description=(
            "TRACE one item to everything connected to it, across systems. Given a single "
            "starting item, returns the items linked to it: Jira issue links and parent, "
            "Jama upstream/downstream traceability relationships, and Confluence page "
            "links. This is the tool for following the thread from one artefact to "
            "another.\n"
            "\n"
            "Use when asked things like: \"what's linked to REQ-102?\", 'what does SRS-42 "
            "trace to?', 'if we change this requirement, what is affected?', 'which tickets "
            "implement this requirement?', 'show me everything connected to PROJ-123'.\n"
            "\n"
            "Prefer this over jama_search / jira_search / confluence_search whenever the "
            "question is about CONNECTIONS FROM a known item rather than finding items by "
            "their words - searching for an item's name returns things that mention it, "
            "which is not the same as things linked to it. Distinct from jama_get_children, "
            "which returns document-tree containment ('what is filed inside this') rather "
            "than traceability ('what derives from this').\n"
            "\n"
            "Starts from exactly ONE item and follows ONE hop - it does not walk the whole "
            "graph transitively. Set include_text_references=true to also scan the item's "
            "text for identifiers like BMS-451 or SRS-42 and resolve them; that surfaces "
            "links nobody recorded formally, but it is a heuristic, so those results are "
            "marked discovered_via='text'. GENESYS is not yet implemented and will return "
            "an explanatory note rather than results. Always read the 'notes' field: it "
            "says what limited the answer."
        ),
        annotations=READ_ONLY,
    )
    async def list_related_items(
        system: Annotated[
            LinkableSystem,
            Field(description="System the item lives in."),
        ],
        item_id: Annotated[
            str,
            Field(
                description=(
                    "Item identifier: a Jira issue key (BMS-451), a numeric Jama item id, "
                    "or a Confluence page id."
                ),
                min_length=1,
            ),
        ],
        include_text_references: Annotated[
            bool,
            Field(
                default=False,
                description=(
                    "Also scan text for item keys and resolve them. Off by default because "
                    "it is heuristic and costs extra API calls."
                ),
            ),
        ] = False,
    ) -> RelatedItemsResult:
        return await guard(
            "list_related_items",
            lambda: service.list_related_items(
                system, item_id, include_text_references=include_text_references
            ),
        )

    names = ["list_related_items"]
    logger.info("linking_tools_registered", tools=names)
    return names
