"""The GENESYS connector is a placeholder; these pin that it behaves as one."""

import pytest

from mcp_radia.config import ServerSettings
from mcp_radia.connectors.errors import ConnectorNotImplementedError
from mcp_radia.connectors.genesys import GenesysClient, GenesysSettings
from mcp_radia.server import build_server
from tests.conftest import connected_client

pytestmark = pytest.mark.unit


def _client(**overrides: object) -> GenesysClient:
    values: dict[str, object] = {"base_url": "https://genesys.internal:8443"}
    values.update(overrides)
    return GenesysClient(GenesysSettings(_env_file=None, **values))


def test_settings_still_parse_so_env_can_be_staged() -> None:
    """A .env written today must stay valid once the connector is built."""
    settings = GenesysSettings(
        _env_file=None,
        base_url="https://genesys.internal:8443",
        username="u",
        password="p",
    )

    assert settings.api_base == "https://genesys.internal:8443/api/v1"
    assert settings.is_configured is True


def test_the_client_reports_itself_unimplemented() -> None:
    assert _client().is_implemented is False


async def test_operations_raise_not_implemented_even_with_credentials() -> None:
    """Credentials do not make a placeholder work, and the error must say so."""
    client = _client(username="u", password="p")

    with pytest.raises(ConnectorNotImplementedError) as exc_info:
        await client.list_projects()

    assert "placeholder" in str(exc_info.value)
    assert exc_info.value.system == "genesys"


async def test_no_genesys_tools_are_advertised() -> None:
    """A tool that always fails is worse than an absent one."""
    server = build_server(ServerSettings(_env_file=None, environment="test"))

    async with connected_client(server) as session:
        names = {t.name for t in (await session.list_tools()).tools}

    assert not any(name.startswith("genesys_") for name in names)
