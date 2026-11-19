"""Jama-only local server configured by Claude Desktop, never by a bundled .env."""

import os
import sys
from urllib.parse import urlsplit

from mcp.server.mcpserver import MCPServer

from mcp_radia import __version__
from mcp_radia.config import ServerSettings
from mcp_radia.connectors.jama import JamaClient, JamaCredentials, JamaSettings
from mcp_radia.logging import configure_logging
from mcp_radia.server import INSTRUCTIONS, SERVER_NAME
from mcp_radia.tools.jama import register_jama_tools
from mcp_radia.tools.jama_write import register_jama_write_tools


def build_desktop_server() -> MCPServer:
    """Build only Jama tools using the credentials collected by the desktop host."""
    base_url = os.environ.get("JAMA_BASE_URL", "").strip().rstrip("/")
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Enter a valid HTTPS Jama instance root in extension settings.") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or port == 0
        or any(character.isspace() for character in base_url)
    ):
        raise ValueError(
            "Enter your HTTPS Jama instance root in extension settings, "
            "such as https://yourorg.jamacloud.com (no /rest or item URL)."
        )
    credentials = JamaCredentials(
        client_id=os.environ.get("JAMA_CLIENT_ID", "").strip(),
        client_secret=os.environ.get("JAMA_CLIENT_SECRET", "").strip(),
    )
    if not credentials.is_complete:
        raise ValueError(
            "Enter your own Jama OAuth client ID and secret in the Radia Jama extension settings."
        )

    # Pydantic's generated signature omits BaseSettings' supported _env_file override.
    settings = ServerSettings(
        _env_file=None,
        environment="production",
        log_level="INFO",
        service_token="",  # type: ignore[call-arg]
    )
    configure_logging(settings)
    client = JamaClient(
        JamaSettings(_env_file=None, base_url=base_url, verify_ssl=True),  # type: ignore[call-arg]
        credentials,
    )
    server = MCPServer(
        name=SERVER_NAME,
        title="Radia Jama",
        version=__version__,
        instructions=(
            INSTRUCTIONS
            + "\nThis desktop extension exposes only Jama tools, not the other integrations. "
            "To check the connection, list the user's accessible Jama projects. "
            "Never ask the user to put credentials in the conversation."
        ),
        log_level=settings.log_level,
    )
    register_jama_tools(server, client)
    register_jama_write_tools(server, client, settings)
    return server


def main() -> int:
    """Keep stdout exclusively for MCP framing, including on setup errors."""
    try:
        server = build_desktop_server()
    except ValueError as exc:
        print(f"Radia Jama setup error: {exc}", file=sys.stderr)
        return 1
    server.run("stdio")
    return 0
