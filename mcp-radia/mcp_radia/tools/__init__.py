"""MCP tool registration.

Every tool the server exposes is registered from :func:`register_tools`, so
there is exactly one place to look to see the server's full surface area.
"""

from mcp.server.mcpserver import MCPServer

from mcp_radia.config import ServerSettings
from mcp_radia.connectors.atlassian import AtlassianSettings
from mcp_radia.connectors.confluence import ConfluenceClient
from mcp_radia.connectors.genesys import GenesysClient, GenesysSettings
from mcp_radia.connectors.jama import JamaClient, JamaSettings
from mcp_radia.connectors.jira import JiraClient
from mcp_radia.linking.service import LinkingService
from mcp_radia.logging import get_logger
from mcp_radia.tools.confluence import register_confluence_tools
from mcp_radia.tools.genesys import register_genesys_tools
from mcp_radia.tools.jama import register_jama_tools
from mcp_radia.tools.jira import register_jira_tools
from mcp_radia.tools.linking import register_linking_tools

logger = get_logger(__name__)


def register_tools(
    server: MCPServer,
    settings: ServerSettings,
    *,
    jama_client: JamaClient | None = None,
    jira_client: JiraClient | None = None,
    confluence_client: ConfluenceClient | None = None,
    genesys_client: GenesysClient | None = None,
    linking_service: LinkingService | None = None,
) -> list[str]:
    """Register all MCP tools on ``server`` and return their names.

    The names are tracked here rather than read back via ``server.list_tools()``
    because that is a coroutine in the MCP 2.x SDK and this runs during
    synchronous startup.

    Connectors are registered whether or not they are configured: an
    unconfigured one still lists its tools, and each call fails with a message
    naming the variable to set. That keeps tool discovery independent of which
    credentials happen to be present.

    Args:
        server: The MCP server to attach tools to.
        settings: Server settings.
        jama_client: Override the Jama connector (tests).
        jira_client: Override the Jira connector (tests).
        confluence_client: Override the Confluence connector (tests).
        genesys_client: Override the GENESYS connector (tests).
        linking_service: Override the linking service (tests).

    Returns:
        The names of every registered tool, in registration order.
    """
    # Jira and Confluence share one Atlassian Cloud credential set, so they
    # share one settings object unless a caller injects its own client.
    atlassian = AtlassianSettings()

    jama = jama_client or JamaClient(JamaSettings())
    jira = jira_client or JiraClient(atlassian)
    confluence = confluence_client or ConfluenceClient(atlassian)
    genesys = genesys_client or GenesysClient(GenesysSettings())

    registered: list[str] = []
    registered += register_jama_tools(server, jama)
    registered += register_jira_tools(server, jira)
    registered += register_confluence_tools(server, confluence)
    # Registers nothing today: the GENESYS connector is a placeholder.
    registered += register_genesys_tools(server, genesys)
    # Linking reuses the same connector instances, so it shares their
    # connection pools and cached auth tokens rather than opening its own.
    registered += register_linking_tools(
        server,
        linking_service
        or LinkingService(jama=jama, jira=jira, confluence=confluence, genesys=genesys),
    )
    logger.debug("tools_registered", tools=registered, count=len(registered))
    return registered
