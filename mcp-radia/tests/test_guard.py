"""Tests for the tool-layer error translation in ``mcp_radia.tools._guard``."""

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mcp_radia.tools._guard import guard

pytestmark = pytest.mark.unit


async def test_an_invalid_argument_reaches_the_model_as_a_readable_tool_error() -> None:
    """A ValueError's hint must not be masked as a generic 'Error executing tool'."""

    async def call() -> None:
        raise ValueError("Jama item ids are numeric; got 'SAND-ACR-1160'.")

    with pytest.raises(ToolError, match="numeric; got 'SAND-ACR-1160'"):
        await guard("list_related_items", call)


async def test_an_unexpected_error_is_not_turned_into_a_tool_error() -> None:
    async def call() -> None:
        raise RuntimeError("internal detail")

    with pytest.raises(RuntimeError):
        await guard("jama_get_item", call)
