"""Phase 0 smoke tests: the server builds, starts, and speaks MCP."""

import pytest
from mcp.server.mcpserver import MCPServer

from mcp_radia import __version__, cli
from mcp_radia.cli import build_parser
from mcp_radia.config import ServerSettings, get_settings
from mcp_radia.server import SERVER_NAME
from tests.conftest import connected_client


@pytest.mark.unit
def test_build_server_reports_identity(server: MCPServer) -> None:
    assert server.name == SERVER_NAME
    assert server.version == __version__


@pytest.mark.unit
async def test_every_registered_tool_is_read_only(server: MCPServer) -> None:
    """The server-wide read-only guarantee, asserted across whatever is registered."""
    tools = await server.list_tools()

    assert tools, "expected at least one tool to be registered"
    for tool in tools:
        assert tool.annotations is not None, f"{tool.name} has no annotations"
        assert tool.annotations.read_only_hint is True, f"{tool.name} is not marked read-only"


@pytest.mark.unit
async def test_mcp_client_completes_handshake_and_lists_tools(server: MCPServer) -> None:
    """End-to-end over real MCP framing: initialize, then tools/list."""
    async with connected_client(server) as session:
        result = await session.list_tools()

    # Deliberately an exact set: this is the one test that must be updated
    # when the server's surface area changes, so growth is never accidental.
    assert {t.name for t in result.tools} == {
        "jama_get_item",
        "jama_search",
        "jama_get_children",
        "jama_list_projects",
        "jira_get_issue",
        "jira_search",
        "confluence_get_page",
        "confluence_search",
        "list_related_items",
    }


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


@pytest.mark.unit
def test_stdio_acts_as_the_local_users_own_jama_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JAMA_CLIENT_ID", "my-client")
    monkeypatch.setenv("JAMA_CLIENT_SECRET", "my-secret")
    captured: dict[str, object] = {}

    class _FakeServer:
        def run(self, transport: str) -> None:
            captured["transport"] = transport

    def _fake_build_server(settings, **kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return _FakeServer()

    monkeypatch.setattr(cli, "build_server", _fake_build_server)

    assert cli.main(["stdio"]) == 0

    credentials = captured["jama_credentials"]
    assert captured["transport"] == "stdio"
    assert credentials is not None
    assert credentials.client_id == "my-client"  # type: ignore[attr-defined]


@pytest.mark.unit
def test_http_never_loads_jama_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Over HTTP there is no shared account: the server-wide Jama client has no identity."""
    monkeypatch.setenv("JAMA_CLIENT_ID", "someone-elses-client")
    monkeypatch.setenv("JAMA_CLIENT_SECRET", "someone-elses-secret")
    monkeypatch.setenv("JAMA_BASE_URL", "https://example.jamacloud.com")
    import mcp_radia.tools as tools_module
    from mcp_radia.asgi import build_http_app

    registered: list[object] = []
    real_register = tools_module.register_jama_tools

    def _spy(server, client):  # type: ignore[no-untyped-def]
        registered.append(client)
        return real_register(server, client)

    monkeypatch.setattr(tools_module, "register_jama_tools", _spy)

    build_http_app(
        ServerSettings(_env_file=None, environment="test", service_token="t"), stateless=True
    )

    (jama_client,) = registered
    assert jama_client.credentials is None  # type: ignore[attr-defined]
    assert jama_client.settings.base_url == "https://example.jamacloud.com"  # type: ignore[attr-defined]
