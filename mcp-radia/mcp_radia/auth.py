"""Service-to-service authentication for the Streamable HTTP transport.

The MCP SDK's ``AuthSettings``/``TokenVerifier`` machinery models a full OAuth
resource server (issuer metadata, protected-resource metadata, scopes) aimed
at user-facing clients. This server has exactly one legitimate caller - the
RadiaAI backend, over a private network - so it uses a much smaller
mechanism: a single shared bearer token, checked on every request before it
reaches the MCP protocol handler.

This is a defense-in-depth layer, not the only one. It assumes the deployment
also binds the HTTP transport to a private/internal network (see the
Container Apps template) so the port itself is never reachable from the
public internet.
"""

import hmac

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from mcp_radia.logging import get_logger

logger = get_logger(__name__)

#: Header a caller must present the shared service token in.
SERVICE_TOKEN_HEADER = "Authorization"  # noqa: S105 (header name, not a secret)
_SCHEME_PREFIX = "Bearer "


class ServiceTokenMiddleware(BaseHTTPMiddleware):
    """Reject any request that does not carry the configured bearer token.

    Compares with :func:`hmac.compare_digest` so response timing cannot be
    used to guess the token one character at a time.
    """

    def __init__(self, app: ASGIApp, *, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        presented = request.headers.get(SERVICE_TOKEN_HEADER, "")
        if not presented.startswith(_SCHEME_PREFIX) or not hmac.compare_digest(
            presented[len(_SCHEME_PREFIX) :], self._token
        ):
            logger.warning("mcp_service_auth_rejected", path=request.url.path)
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


def require_service_token(app: Starlette, *, token: str) -> Starlette:
    """Wrap ``app`` so every request must carry the shared service token.

    Raises ``ValueError`` rather than silently serving an unauthenticated
    server: an empty token almost always means an operator forgot to set
    ``MCP_RADIA_SERVICE_TOKEN``, not that auth should be skipped.
    """
    if not token:
        raise ValueError(
            "MCP_RADIA_SERVICE_TOKEN must be set to run the HTTP transport. "
            "Generate one (e.g. `openssl rand -hex 32`) and configure the same "
            "value on the RadiaAI backend's MCP client."
        )
    app.add_middleware(ServiceTokenMiddleware, token=token)
    return app
