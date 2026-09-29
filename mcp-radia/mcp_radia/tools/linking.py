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
            "Trace one item to the items related to it. Reads each system's own "
            "cross-references live: Jira issue links and parent, Jama upstream/downstream "
            "relationships, Confluence page links. Set include_text_references to also "
            "scan the item's text for identifiers like BMS-451 or SRS-42 and resolve them "
            "against Jira and Jama - that finds links nobody recorded formally, but it is "
            "a heuristic, so those results are marked discovered_via='text'. Always read "
            "the 'notes' field: it says what limited the answer."
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
