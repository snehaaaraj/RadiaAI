"""Shared test fixtures for the mcp-radia test suite.

No test in this suite may touch the network. Connector tests in later phases
mock HTTP at the transport layer; the tests here drive the MCP server itself
over in-memory streams, so nothing binds a port or spawns a process.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.server.mcpserver import MCPServer
from mcp.shared.memory import create_client_server_memory_streams

from mcp_radia.config import ServerSettings
from mcp_radia.connectors.jama import JamaClient, JamaSettings
from mcp_radia.server import build_server


@pytest.fixture
def settings() -> ServerSettings:
    """Settings with explicit values, independent of any .env on the machine."""
    return ServerSettings(_env_file=None, environment="test", log_level="DEBUG")


@pytest.fixture
def server(settings: ServerSettings) -> MCPServer:
    """A server whose connectors are deliberately unconfigured.

    Passing an explicit unconfigured JamaClient stops the fixture reading a
    developer's real mcp-radia/.env, so no test can reach a live system by
    accident. Tests that need working connectors build their own server.
    """
    unconfigured_jama = JamaClient(JamaSettings(_env_file=None, base_url=""))
    return build_server(settings, jama_client=unconfigured_jama)


@asynccontextmanager
async def connected_client(server: MCPServer) -> AsyncIterator[ClientSession]:
    """Run ``server`` in a background task with a real ClientSession wired to it.

    Reaches for the SDK's private ``_lowlevel_server`` because that is the only
    way to drive an MCPServer over arbitrary streams; the public ``run()`` owns
    the transport. Confined to this helper so an SDK change breaks one place.
    """
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        client_read, client_write = client_streams
        server_read, server_write = server_streams
        lowlevel = server._lowlevel_server
        init_options = lowlevel.create_initialization_options()

        async with anyio.create_task_group() as task_group:

            async def _serve() -> None:
                await lowlevel.run(server_read, server_write, init_options, raise_exceptions=True)

            task_group.start_soon(_serve)
            async with ClientSession(client_read, client_write) as session:
                await session.initialize()
                yield session
            task_group.cancel_scope.cancel()


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if any test tries to reach a host off this machine.

    The suite is meant to be entirely offline: connectors are driven through
    httpx2.MockTransport and the MCP server through in-memory streams. This
    turns "we think nothing calls out" into something enforced, so a future
    connector cannot quietly start hitting a live Jama instance in CI.

    Loopback stays open because asyncio's Windows proactor loop builds its
    self-pipe from a real socketpair over 127.0.0.1.
    """
    import socket

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def _is_loopback(address: object) -> bool:
        if not isinstance(address, tuple) or not address:
            return True  # AF_UNIX and friends never leave the machine.
        host = str(address[0])
        return host in {"127.0.0.1", "::1", "localhost", ""}

    def _guarded(original):  # type: ignore[no-untyped-def]
        def _inner(self, address, *args, **kwargs):  # type: ignore[no-untyped-def]
            if not _is_loopback(address):
                raise RuntimeError(
                    f"This test attempted a real network connection to {address!r}. "
                    "Tests must mock HTTP (see tests/jama_fixtures.py)."
                )
            return original(self, address, *args, **kwargs)

        return _inner

    monkeypatch.setattr(socket.socket, "connect", _guarded(real_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", _guarded(real_connect_ex))

    # Resolution is itself a network call, and an unresolvable hostname would
    # otherwise fail here with a DNS error that looks nothing like "you tried
    # to call out" - so catch it at the name lookup too.
    real_getaddrinfo = socket.getaddrinfo

    def _guarded_getaddrinfo(host, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not _is_loopback((host,)):
            raise RuntimeError(
                f"This test attempted to resolve {host!r}. "
                "Tests must mock HTTP (see tests/jama_fixtures.py)."
            )
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", _guarded_getaddrinfo)
