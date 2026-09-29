"""MCP tool registration.

Every tool the server exposes is registered from :func:`register_tools`, so
there is exactly one place to look to see the server's full surface area.
"""

from mcp.server.mcpserver import MCPServer

from mcp_radia.config import ServerSettings
from mcp_radia.connectors.jama import JamaClient, JamaSettings
from mcp_radia.logging import get_logger
from mcp_radia.tools.jama import register_jama_tools

logger = get_logger(__name__)


def register_tools(
    server: MCPServer,
    settings: ServerSettings,
    *,
    jama_client: JamaClient | None = None,
) -> list[str]:
    """Register all MCP tools on ``server`` and return their names.

    The names are tracked here rather than read back via ``server.list_tools()``
    because that is a coroutine in the MCP 2.x SDK and this runs during
    synchronous startup.

    Args:
        server: The MCP server to attach tools to.
        settings: Server settings, passed through to connectors that need them.
        jama_client: Override the Jama connector. Tests inject a client backed
            by a mock HTTP transport; in production it is built from the
            ``JAMA_*`` environment.

    Returns:
        The names of every registered tool, in registration order.
    """
    registered: list[str] = []
    registered += register_jama_tools(server, jama_client or JamaClient(JamaSettings()))
    # Phases 2-4 extend this list: Jira, Confluence, Genesys, cross-system linking.
    logger.debug("tools_registered", tools=registered)
    return registered
