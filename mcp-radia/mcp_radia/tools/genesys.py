"""GENESYS MCP tools - **none registered yet**.

The GENESYS connector is a placeholder (see
:mod:`mcp_radia.connectors.genesys` for why), so this registers nothing. A tool
that is advertised but always fails is worse than an absent one: the model
would keep choosing it and keep failing.

The wiring is kept in place so that enabling GENESYS later is a matter of
filling in this function, not re-threading registration through the server.

Planned surface, once the REST contract is confirmed:

  - ``genesys_list_projects``    - entities are addressed within a project, so
                                   a project id has to be discoverable first.
  - ``genesys_get_entity``       - an entity plus its typed relationships.
  - ``genesys_search_entities``  - search within a project by text and class.
"""

from mcp.server.mcpserver import MCPServer

from mcp_radia.connectors.genesys import GenesysClient
from mcp_radia.logging import get_logger

logger = get_logger(__name__)


def register_genesys_tools(server: MCPServer, client: GenesysClient) -> list[str]:
    """Register the GENESYS tools. Currently a no-op; returns an empty list."""
    logger.info(
        "genesys_tools_skipped",
        reason="connector is a placeholder pending REST contract confirmation",
        credentials_staged=client.is_configured,
    )
    return []
