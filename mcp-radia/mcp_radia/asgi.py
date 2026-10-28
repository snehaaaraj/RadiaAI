"""Shared construction of the service-token-protected Streamable HTTP ASGI app.

Used by two entry points that need the identical app, built two different ways:

  - ``mcp_radia.cli`` (``mcp-radia http``) - a long-running process, so it uses
    *stateful* mode: a session persists in memory across requests, which saves
    a repeated ``initialize`` handshake per tool call.
  - ``api/index.py`` (Vercel) - a serverless function, where consecutive
    requests are not guaranteed to reach the same process, so no in-memory
    session could survive between them anyway. It uses *stateless* mode: every
    request is self-contained, matching the Streamable HTTP spec's stateless
    operation (see the MCP SDK's ``streamable_http_manager`` docstring).

Both still require the identical bearer-token check from :mod:`mcp_radia.auth`:
statelessness is a protocol detail, not a relaxation of the service boundary.
"""

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from mcp_radia.auth import require_service_token
from mcp_radia.config import ServerSettings, get_settings
from mcp_radia.server import build_server


def build_http_app(settings: ServerSettings | None = None, *, stateless: bool) -> Starlette:
    """Build the token-protected Streamable HTTP ASGI app.

    Raises ``ValueError`` (via :func:`require_service_token`) if
    ``MCP_RADIA_SERVICE_TOKEN`` is not set - this app must never serve a
    request with no bearer-token check in front of it.
    """
    resolved = settings or get_settings()
    server = build_server(resolved)

    # The SDK auto-restricts the Host header to loopback-only values whenever
    # `host` is 127.0.0.1/localhost/::1 (MCP_RADIA_HOST's default) - exactly
    # right for `cli.py`'s own local HTTP listener, but wrong for a public
    # serverless deployment: the real inbound Host there is the deployment's
    # own domain (e.g. *.vercel.app), which the auto-detection has never seen
    # and would reject with HTTP 421 on every single request. Disable that
    # Host-header check here explicitly rather than rely on the auto-detected
    # default; the bearer-token check in mcp_radia.auth is this deployment's
    # actual access boundary, same as it already is for the stateful path.
    transport_security = (
        TransportSecuritySettings(enable_dns_rebinding_protection=False) if stateless else None
    )

    app = server.streamable_http_app(
        streamable_http_path=resolved.http_path,
        host=resolved.host,
        stateless_http=stateless,
        transport_security=transport_security,
    )
    return require_service_token(app, token=resolved.service_token)
