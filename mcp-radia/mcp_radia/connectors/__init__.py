"""Read-only connectors to RadiaAI's external systems of record.

Each connector owns its own settings class, its own HTTP client and its own
mapping from the vendor's JSON into Pydantic models. They share only the
exception hierarchy in :mod:`mcp_radia.connectors.errors`, so the tool layer can
translate any connector failure into an MCP error the same way.

Every connector in this package is **read-only**: search and get, nothing else.
"""
