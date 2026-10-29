"""Per-user credential passthrough for the Jama tools.

The RadiaAI backend already knows which Jama account each signed-in user has
linked (see the backend's ``JamaAccountService``). To make Jama tool calls act
as that user - so Jama itself enforces which projects and items they can
read - the backend forwards that user's OAuth client-credentials pair on each
MCP request as a pair of headers, and this module builds a Jama connector
scoped to just that one request.

There is no shared Jama account to fall back to. Over Streamable HTTP the
server-wide client carries no credentials, so a call without these headers
fails asking the user to link their Jama account. Over stdio the server-wide
client carries the local user's own credentials (``JAMA_CLIENT_ID`` /
``JAMA_CLIENT_SECRET``), which is the same person sitting at the client.

Jira and Confluence are not covered here: they remain on the server's
Atlassian credential (see mcp-radia/.env.example) until per-user Atlassian
linking exists in the backend.

These headers are only trustworthy because the Streamable HTTP transport sits
behind the service-token check in :mod:`mcp_radia.auth` and a private network:
nothing here re-authenticates them.
"""

from mcp.server.mcpserver import Context

from mcp_radia.connectors.jama import JamaClient, JamaCredentials
from mcp_radia.logging import get_logger

logger = get_logger(__name__)

#: Carries the signed-in user's linked Jama OAuth client id, forwarded by the backend.
JAMA_CLIENT_ID_HEADER = "X-Radia-Jama-Client-Id"
#: Carries the matching OAuth client secret. Never logged.
JAMA_CLIENT_SECRET_HEADER = "X-Radia-Jama-Client-Secret"  # noqa: S105 (header name, not a secret)


def jama_client_for_request(ctx: Context, server_client: JamaClient) -> tuple[JamaClient, bool]:
    """Return the Jama client to use for this call, and whether it is request-scoped.

    With both per-user headers present, returns a new client acting as that
    user; the caller must ``aclose()`` it after use. Otherwise returns
    ``server_client`` unchanged - which over HTTP has no credentials and so
    fails the call with a "link your Jama account" message, and over stdio
    acts as the local user. ``server_client`` lives for the server's lifetime
    and must NOT be closed by the caller.

    Connection settings (base URL, API version, timeout, TLS) always come from
    the server's own configuration, never from the request.
    """
    headers = ctx.headers or {}
    credentials = JamaCredentials(
        client_id=headers.get(JAMA_CLIENT_ID_HEADER, "").strip(),
        client_secret=headers.get(JAMA_CLIENT_SECRET_HEADER, "").strip(),
    )
    if not credentials.is_complete:
        return server_client, False
    return server_client.with_credentials(credentials), True
