"""Failures raised by the MCP client adapter.

Every failure here is meant to be caught by the chat orchestration layer and
turned into a safe, user-facing message - never an unhandled 500 and never a
raw upstream error (which could carry internal hostnames or stack traces).
"""


class MCPError(Exception):
    """Base class for every failure raised by the MCP client adapter."""


class MCPDisabledError(MCPError):
    """MCP is not enabled or not fully configured on this deployment."""


class MCPUnavailableError(MCPError):
    """The MCP server could not be reached, timed out, or the transport failed."""


class MCPProtocolError(MCPError):
    """The MCP server returned a malformed or unexpected JSON-RPC response."""


class MCPResponseTooLargeError(MCPError):
    """A tool result exceeded the configured size limit."""


class MCPToolNotAllowedError(MCPError):
    """The requested tool is not on the server-side allowlist.

    Raised whether the tool is unknown to mcp-radia entirely or merely absent
    from ``MCPSettings.allowed_tools`` - the model never learns which.
    """


class MCPToolArgumentsInvalidError(MCPError):
    """The requested tool's arguments failed validation against its schema."""


class MCPToolExecutionError(MCPError):
    """mcp-radia reported the tool call itself failed (``isError`` on the result)."""
