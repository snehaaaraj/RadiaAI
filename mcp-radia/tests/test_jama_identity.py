"""Tests for per-user Jama credential passthrough (mcp_radia.tools._identity)."""

from collections.abc import Mapping

import pytest

from mcp_radia.connectors.jama import JamaClient
from mcp_radia.tools._identity import (
    JAMA_CLIENT_ID_HEADER,
    JAMA_CLIENT_SECRET_HEADER,
    jama_client_for_request,
)
from tests.jama_fixtures import CREDENTIALS, jama_settings

pytestmark = pytest.mark.unit


class _FakeContext:
    """Stands in for ``mcp.server.mcpserver.Context``: only ``.headers`` is read."""

    def __init__(self, headers: Mapping[str, str] | None) -> None:
        self.headers = headers


_USER_HEADERS = {
    JAMA_CLIENT_ID_HEADER: "user-client-id",
    JAMA_CLIENT_SECRET_HEADER: "user-client-secret",
}


@pytest.mark.parametrize(
    "headers",
    [
        None,
        {JAMA_CLIENT_ID_HEADER: "user-client-id"},
        {JAMA_CLIENT_ID_HEADER: "  ", JAMA_CLIENT_SECRET_HEADER: "  "},
    ],
)
def test_http_server_without_headers_has_no_account_to_act_as(
    headers: Mapping[str, str] | None,
) -> None:
    """There is no shared Jama account: an HTTP server-wide client has no identity."""
    server_client = JamaClient(jama_settings())

    client, owned = jama_client_for_request(_FakeContext(headers), server_client)

    assert client is server_client
    assert owned is False
    assert client.credentials is None
    assert client.is_configured is False


def test_stdio_server_without_headers_acts_as_the_local_user() -> None:
    server_client = JamaClient(jama_settings(), CREDENTIALS)

    client, owned = jama_client_for_request(_FakeContext(None), server_client)

    assert client is server_client
    assert owned is False
    assert client.credentials == CREDENTIALS


@pytest.mark.parametrize("local_credentials", [None, CREDENTIALS])
def test_builds_request_scoped_client_from_headers(local_credentials) -> None:  # type: ignore[no-untyped-def]
    server_client = JamaClient(jama_settings(), local_credentials)

    client, owned = jama_client_for_request(_FakeContext(_USER_HEADERS), server_client)

    assert owned is True
    assert client is not server_client
    assert client.credentials is not None
    assert client.credentials.client_id == "user-client-id"
    assert client.credentials.client_secret == "user-client-secret"
    # Base URL and other connection settings come from the server's own
    # configuration, not from the (untrusted) request - only identity differs.
    assert client.settings is server_client.settings
