"""Jama-only desktop setup and the distributable archive contract."""

import json
import shutil
import tomllib
from pathlib import Path
from zipfile import ZipFile

import pytest
from build_desktop import build_bundle

from mcp_radia import __version__, desktop
from mcp_radia.connectors.jama import JamaClient
from tests.conftest import connected_client
from tests.jama_fixtures import PROJECTS_PAYLOAD, json_responder, make_client
from tests.test_jama_write import fixture_client

pytestmark = pytest.mark.unit
PROJECT = Path(__file__).resolve().parents[1]
JAMA_TOOLS = {
    "jama_get_item",
    "jama_search",
    "jama_get_children",
    "jama_get_relationships",
    "jama_list_projects",
    "jama_get_item_type",
    "jama_get_picklist",
    "jama_prepare_field_update",
    "jama_confirm_field_update",
}


@pytest.fixture
def desktop_env(monkeypatch):
    monkeypatch.setenv("JAMA_BASE_URL", "https://example.jamacloud.com/")
    monkeypatch.setenv("JAMA_CLIENT_ID", "desktop-test-client")
    monkeypatch.setenv("JAMA_CLIENT_SECRET", "desktop-test-secret")


async def test_desktop_exposes_exactly_the_manifest_jama_tools(desktop_env):
    manifest = json.loads((PROJECT / "manifest.json").read_text(encoding="utf-8"))
    server = desktop.build_desktop_server()
    assert server.title == "Radia MCP"
    assert manifest["display_name"] == "Radia MCP"
    assert manifest["name"] == "radia-jama"
    async with connected_client(server) as session:
        tools = (await session.list_tools()).tools

    assert {tool.name for tool in tools} == JAMA_TOOLS
    assert {tool["name"] for tool in manifest["tools"]} == JAMA_TOOLS
    assert manifest["version"] == __version__
    for tool in tools:
        assert tool.annotations.read_only_hint is (tool.name != "jama_confirm_field_update")


def test_desktop_uses_entered_credentials_and_requires_tls(desktop_env, monkeypatch):
    captured = {}

    def create_client(settings, credentials):
        captured.update(settings=settings, credentials=credentials)
        return JamaClient(settings, credentials)

    monkeypatch.setenv("JAMA_VERIFY_SSL", "false")
    monkeypatch.setattr(desktop, "JamaClient", create_client)
    desktop.build_desktop_server()
    assert captured["settings"].base_url == "https://example.jamacloud.com"
    assert captured["settings"].verify_ssl is True
    assert captured["credentials"].client_id == "desktop-test-client"
    assert captured["credentials"].client_secret == "desktop-test-secret"


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://example.jamacloud.com",
        "https://example.jamacloud.com/rest/v1",
        "https://example.jamacloud.com/perspective.req#/items/1",
        "https://user:password@example.jamacloud.com",
        "https://example.jamacloud.com?token=secret",
        "https://",
        "https://[invalid",
        "https://example.jamacloud.com:invalid",
        "https://example.jamacloud.com:0",
        "https://example .jamacloud.com",
        "https://example.jama\ncloud.com",
    ],
)
def test_desktop_rejects_unsafe_or_nonroot_urls(desktop_env, monkeypatch, capsys, url):
    monkeypatch.setenv("JAMA_BASE_URL", url)
    assert desktop.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "Radia MCP setup error" in output.err
    assert "desktop-test-secret" not in output.err
    assert "user:password" not in output.err
    assert "token=secret" not in output.err


@pytest.mark.parametrize("variable", ["JAMA_CLIENT_ID", "JAMA_CLIENT_SECRET", "JAMA_BASE_URL"])
def test_desktop_never_falls_back_to_developer_dotenv(desktop_env, monkeypatch, variable):
    # Even on a developer machine with mcp-radia/.env, missing host config fails.
    monkeypatch.delenv(variable)
    with pytest.raises(ValueError):
        desktop.build_desktop_server()


def test_desktop_runs_stdio_only(desktop_env, monkeypatch):
    calls = []

    class FakeServer:
        def run(self, transport):
            calls.append(transport)

    monkeypatch.setattr(desktop, "build_desktop_server", FakeServer)
    assert desktop.main() == 0
    assert calls == ["stdio"]


async def test_desktop_can_read_jama_projects(desktop_env, monkeypatch):
    captured = {}

    def create_client(settings, credentials):
        client, handler = make_client(
            settings, json_responder(PROJECTS_PAYLOAD), credentials=credentials
        )
        captured["handler"] = handler
        return client

    monkeypatch.setattr(desktop, "JamaClient", create_client)
    async with connected_client(desktop.build_desktop_server()) as session:
        result = await session.call_tool("jama_list_projects", {})
    assert not result.is_error
    assert result.structured_content is not None
    assert captured["handler"].last_request.url.path == "/rest/v1/projects"


async def test_desktop_preserves_confirmed_write_contract(desktop_env, monkeypatch):
    client, _, raw, patches = fixture_client()
    monkeypatch.setattr(desktop, "JamaClient", lambda *args: client)
    async with connected_client(desktop.build_desktop_server()) as session:
        prepared = await session.call_tool(
            "jama_prepare_field_update",
            {"item_id": 12345, "fields": {"Description": "Desktop approved text"}},
        )
        assert not prepared.is_error
        assert patches == []
        token = prepared.structured_content["confirmation_token"]
        denied = await session.call_tool(
            "jama_confirm_field_update", {"confirmation_token": token, "confirmed": False}
        )
        assert denied.is_error
        assert patches == []
        written = await session.call_tool(
            "jama_confirm_field_update", {"confirmation_token": token, "confirmed": True}
        )
    assert not written.is_error
    assert len(patches) == 1
    assert raw["fields"]["description"] == "<p>Desktop approved text</p>"


def test_manifest_guides_setup_without_plaintext_credentials():
    manifest = json.loads((PROJECT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == "0.4"
    assert manifest["server"]["type"] == "uv"
    assert set(manifest["compatibility"]["platforms"]) == {"darwin", "win32"}
    for key in ("jama_base_url", "jama_client_id", "jama_client_secret"):
        assert manifest["user_config"][key]["required"] is True
        assert "default" not in manifest["user_config"][key]
    for key in ("jama_client_id", "jama_client_secret"):
        assert manifest["user_config"][key]["sensitive"] is True
    config = manifest["server"]["mcp_config"]
    assert config["env"] == {
        "JAMA_BASE_URL": "${user_config.jama_base_url}",
        "JAMA_CLIENT_ID": "${user_config.jama_client_id}",
        "JAMA_CLIENT_SECRET": "${user_config.jama_client_secret}",
    }
    assert "--locked" in config["args"]


def test_bundle_includes_runtime_but_no_local_environment(tmp_path):
    project = tmp_path / "source"
    project.mkdir()
    for name in ("manifest.json", "pyproject.toml", "uv.lock", "README.md"):
        shutil.copyfile(PROJECT / name, project / name)
    for name in ("desktop/server.py", "mcp_radia/__init__.py", "mcp_radia/desktop.py"):
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT / name, target)
    for name in (
        ".env",
        ".env.example",
        ".venv/secret.py",
        "tests/secret.py",
        "mcp_radia/.env",
        "mcp_radia/__pycache__/secret.pyc",
    ):
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("must-not-ship", encoding="utf-8")

    bundle = build_bundle(project, tmp_path / "output")
    with ZipFile(bundle) as archive:
        assert set(archive.namelist()) == {
            "manifest.json",
            "pyproject.toml",
            "uv.lock",
            "README.md",
            "desktop/server.py",
            "mcp_radia/__init__.py",
            "mcp_radia/desktop.py",
        }
        assert all(b"must-not-ship" not in archive.read(name) for name in archive.namelist())
        tomllib.loads(archive.read("uv.lock").decode())
        assert archive.testzip() is None


def test_bundle_refuses_mismatched_versions(tmp_path):
    (tmp_path / "manifest.json").write_text('{"name": "radia-jama", "version": "99.0.0"}')
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n')
    with pytest.raises(ValueError, match="version"):
        build_bundle(tmp_path, tmp_path / "output")


def test_bundle_refuses_missing_runtime_files(tmp_path):
    for name in ("manifest.json", "pyproject.toml"):
        shutil.copyfile(PROJECT / name, tmp_path / name)
    with pytest.raises(ValueError, match=r"uv\.lock"):
        build_bundle(tmp_path, tmp_path / "output")
    assert not (tmp_path / "output").exists()
