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
from mcp_radia.server import build_server


@pytest.fixture
def settings() -> ServerSettings:
    """Settings with explicit values, independent of any .env on the machine."""
    return ServerSettings(environment="test", log_level="DEBUG")


@pytest.fixture
def server(settings: ServerSettings) -> MCPServer:
    return build_server(settings)


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
