"""Per-user credential passthrough for tools that support it.

The RadiaAI backend already knows which Jama account each signed-in user has
linked (see the backend's ``JamaAccountService``). To make Jama tool calls act
as that user - so Jama itself enforces which projects and items they can
read - the backend forwards that user's OAuth client-credentials pair on each
MCP request as a pair of headers, and this module builds a Jama connector
scoped to just that one request.

Only Jama supports this today: Jira and Confluence remain on the server's
shared Atlassian credential (see mcp-radia/.env.example) until per-user
Atlassian linking exists in the backend.

These headers are only trustworthy because the Streamable HTTP transport sits
behind the service-token check in :mod:`mcp_radia.auth` and a private network:
nothing here re-authenticates them.
"""

from mcp.server.mcpserver import Context

from mcp_radia.connectors.jama import JamaClient, JamaSettings
from mcp_radia.logging import get_logger

logger = get_logger(__name__)

#: Carries the signed-in user's linked Jama OAuth client id, forwarded by the backend.
JAMA_CLIENT_ID_HEADER = "X-Radia-Jama-Client-Id"
#: Carries the matching OAuth client secret. Never logged.
JAMA_CLIENT_SECRET_HEADER = "X-Radia-Jama-Client-Secret"  # noqa: S105 (header name, not a secret)


def jama_client_for_request(ctx: Context, shared: JamaClient) -> tuple[JamaClient, bool]:
    """Return the Jama client to use for this call, and whether it is request-scoped.

    Falls back to ``shared`` (the server's own configured client) when the
    per-user headers are absent - stdio transport, local development, or a
    caller that has not linked a Jama account. The caller must ``aclose()``
    a request-scoped client after use; it must NOT close ``shared``, which
    lives for the server's lifetime.
    """
    headers = ctx.headers or {}
    client_id = headers.get(JAMA_CLIENT_ID_HEADER, "").strip()
    client_secret = headers.get(JAMA_CLIENT_SECRET_HEADER, "").strip()
    if not client_id or not client_secret:
        return shared, False

    base = shared.settings
    per_user_settings = JamaSettings(
        base_url=base.base_url,
        auth_type="oauth",
        client_id=client_id,
        client_secret=client_secret,
        api_version=base.api_version,
        timeout_seconds=base.timeout_seconds,
        verify_ssl=base.verify_ssl,
    )
    return JamaClient(per_user_settings), True
