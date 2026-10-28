"""MCP (Model Context Protocol) chat integration.

Lets the chat pipeline call read-only tools on the ``mcp-radia`` server. See
:class:`~app.services.mcp.client.MCPClientAdapter` for the entry point other
modules should use; nothing else in the backend should import
:mod:`app.services.mcp.transport` directly.
"""
