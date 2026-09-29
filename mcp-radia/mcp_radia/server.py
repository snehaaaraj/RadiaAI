"""Construction of the RadiaAI digital-thread MCP server."""

from mcp.server.mcpserver import MCPServer

from mcp_radia import __version__
from mcp_radia.config import ServerSettings
from mcp_radia.logging import get_logger
from mcp_radia.tools import register_tools

logger = get_logger(__name__)

SERVER_NAME = "radia-digital-thread"

INSTRUCTIONS = """\
Read-only access to RadiaAI's engineering systems of record.

This server is a digital-thread integration layer: it will expose Jama
requirements, Jira issues, Confluence pages and Genesys records through a
single MCP surface so they can be traced against each other.

Every tool on this server is read-only. Nothing here creates, updates or
deletes data in the underlying systems.
"""


def build_server(settings: ServerSettings) -> MCPServer:
    """Build a fully configured MCP server instance.

    Kept separate from the CLI so tests can drive a server over in-memory
    streams without spawning a process or binding a port.
    """
    server = MCPServer(
        name=SERVER_NAME,
        title="RadiaAI Digital Thread",
        version=__version__,
        instructions=INSTRUCTIONS,
        log_level=settings.log_level,
    )
    registered = register_tools(server, settings)
    logger.info(
        "mcp_server_built",
        server_name=SERVER_NAME,
        version=__version__,
        environment=settings.environment,
        tool_count=len(registered),
    )
    return server
