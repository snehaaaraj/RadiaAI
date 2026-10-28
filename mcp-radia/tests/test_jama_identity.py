"""Tests for per-user Jama credential passthrough (mcp_radia.tools._identity)."""

from collections.abc import Mapping

import pytest

from mcp_radia.connectors.jama import JamaClient
from mcp_radia.tools._identity import (
    JAMA_CLIENT_ID_HEADER,
    JAMA_CLIENT_SECRET_HEADER,
    jama_client_for_request,
)
from tests.jama_fixtures import basic_settings

pytestmark = pytest.mark.unit


class _FakeContext:
    """Stands in for ``mcp.server.mcpserver.Context``: only ``.headers`` is read."""

    def __init__(self, headers: Mapping[str, str] | None) -> None:
        self.headers = headers


def test_falls_back_to_shared_client_when_no_headers() -> None:
    shared = JamaClient(basic_settings())

    client, owned = jama_client_for_request(_FakeContext(None), shared)

    assert client is shared
    assert owned is False


def test_falls_back_when_only_one_header_present() -> None:
    shared = JamaClient(basic_settings())
    ctx = _FakeContext({JAMA_CLIENT_ID_HEADER: "user-client-id"})

    client, owned = jama_client_for_request(ctx, shared)

    assert client is shared
    assert owned is False


def test_builds_request_scoped_oauth_client_from_headers() -> None:
    shared = JamaClient(basic_settings(base_url="https://example.jamacloud.com"))
    ctx = _FakeContext(
        {
            JAMA_CLIENT_ID_HEADER: "user-client-id",
            JAMA_CLIENT_SECRET_HEADER: "user-client-secret",
        }
    )

    client, owned = jama_client_for_request(ctx, shared)

    assert owned is True
    assert client is not shared
    assert client.settings.auth_type == "oauth"
    assert client.settings.client_id == "user-client-id"
    assert client.settings.client_secret == "user-client-secret"
    # Base URL and other connection settings come from the server's own
    # configuration, not from the (untrusted) request - only identity differs.
    assert client.settings.base_url == shared.settings.base_url


def test_ignores_blank_headers() -> None:
    shared = JamaClient(basic_settings())
    ctx = _FakeContext({JAMA_CLIENT_ID_HEADER: "  ", JAMA_CLIENT_SECRET_HEADER: "  "})

    client, owned = jama_client_for_request(ctx, shared)

    assert client is shared
    assert owned is False
