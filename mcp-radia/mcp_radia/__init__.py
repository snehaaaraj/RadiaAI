"""RadiaAI digital-thread MCP server.

A standalone Model Context Protocol server that will expose read-only views of
Jira, Confluence, Jama and Genesys as MCP tools.

This package is intentionally independent of the RadiaAI ``backend/`` service:
it has its own dependencies, its own configuration, and its own tests, and it
must never import from ``app`` or ``radia_ai``.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
