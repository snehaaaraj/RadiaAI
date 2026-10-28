"""Vercel serverless entry point for mcp-radia.

Mirrors ``backend/api/index.py``'s pattern: export a module-level ASGI ``app``
that the ``@vercel/python`` builder discovers and routes all traffic to (see
``vercel.json`` alongside this file).

Built in *stateless* Streamable HTTP mode (see ``mcp_radia.asgi``) because a
serverless deployment gives no guarantee that two requests - even two
requests moments apart from the same backend client - land on the same
warm instance, so no server-side in-memory session could survive between
them regardless of which mode was chosen.
"""

from mcp_radia.asgi import build_http_app
from mcp_radia.config import get_settings
from mcp_radia.logging import configure_logging

_settings = get_settings()
configure_logging(_settings)

app = build_http_app(_settings, stateless=True)

__all__ = ["app"]
