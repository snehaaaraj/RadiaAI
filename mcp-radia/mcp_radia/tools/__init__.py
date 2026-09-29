"""MCP tool registration.

Every tool the server exposes is registered from :func:`register_tools`, so
there is exactly one place to look to see the server's full surface area.

Phase 0 registers nothing on purpose: the scaffold's job is to start up,
complete an MCP handshake and honestly report an empty tool list. Connectors
(Jama, Jira, Confluence, Genesys) each add their tools here as they land.
"""

from mcp.server.mcpserver import MCPServer

from mcp_radia.config import ServerSettings
from mcp_radia.logging import get_logger

logger = get_logger(__name__)


def register_tools(server: MCPServer, settings: ServerSettings) -> list[str]:
    """Register all MCP tools on ``server`` and return their names.

    The names are tracked here rather than read back via ``server.list_tools()``
    because that is a coroutine in the MCP 2.x SDK and this runs during
    synchronous startup.

    Args:
        server: The MCP server to attach tools to.
        settings: Server settings, passed through to connectors that need
            credentials once they exist.

    Returns:
        The names of every registered tool, in registration order.
    """
    registered: list[str] = []
    # Phase 0: no tools yet. Later phases extend this list, e.g.
    #   registered += register_jama_tools(server, settings)
    logger.debug("tools_registered", tools=registered)
    return registered
