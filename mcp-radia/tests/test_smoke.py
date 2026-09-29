"""Phase 0 smoke tests: the server builds, starts, and speaks MCP."""

import pytest
from mcp.server.mcpserver import MCPServer

from mcp_radia import __version__
from mcp_radia.cli import build_parser
from mcp_radia.config import ServerSettings, get_settings
from mcp_radia.server import SERVER_NAME
from tests.conftest import connected_client


@pytest.mark.unit
def test_build_server_reports_identity(server: MCPServer) -> None:
    assert server.name == SERVER_NAME
    assert server.version == __version__


@pytest.mark.unit
async def test_phase_0_registers_no_tools(server: MCPServer) -> None:
    """The scaffold must be honest about exposing nothing yet."""
    assert await server.list_tools() == []


@pytest.mark.unit
async def test_mcp_client_completes_handshake_and_lists_tools(server: MCPServer) -> None:
    """End-to-end over real MCP framing: initialize, then tools/list."""
    async with connected_client(server) as session:
        result = await session.list_tools()

    assert result.tools == []


@pytest.mark.unit
async def test_handshake_advertises_server_info(server: MCPServer) -> None:
    async with connected_client(server) as session:
        # Cached from the handshake connected_client already performed.
        server_info = session.server_info

    assert server_info is not None
    assert server_info.name == SERVER_NAME
    assert server_info.version == __version__


@pytest.mark.unit
def test_stdio_is_the_default_transport() -> None:
    """Running the bare command must not silently bind a port."""
    assert build_parser().parse_args([]).transport is None


@pytest.mark.unit
def test_http_subcommand_accepts_host_and_port_overrides() -> None:
    args = build_parser().parse_args(["http", "--host", "0.0.0.0", "--port", "9000"])

    assert args.transport == "http"
    assert args.host == "0.0.0.0"
    assert args.port == 9000


@pytest.mark.unit
def test_settings_default_to_a_port_that_avoids_the_backend() -> None:
    # _env_file=None so a developer's local mcp-radia/.env cannot fail this test.
    settings = ServerSettings(_env_file=None)

    assert settings.port == 8081, "8000 belongs to the RadiaAI backend"
    assert settings.http_url == "http://127.0.0.1:8081/mcp"


@pytest.mark.unit
def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
