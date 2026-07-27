"""
Security utilities — authentication and authorization stubs for Microsoft Entra ID.

Phase 1: Provides the hook points and placeholder dependency so endpoints compile
and work locally without auth. Phase 2+ will wire in real JWT validation.

The pattern used here (FastAPI Depends on a callable) means that switching from
the stub to real Entra validation requires changing only this file — no endpoint
code needs to change.
"""

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import AppSettings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser:
    """Represents a verified caller after token validation."""

    def __init__(
        self,
        user_id: str,
        email: str,
        roles: list[str],
        display_name: str = "",
    ) -> None:
        self.user_id = user_id
        self.email = email
        self.roles = roles
        self.display_name = display_name

    def has_role(self, role: str) -> bool:
        return role in self.roles


async def _stub_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: AppSettings = Depends(get_settings),
) -> AuthenticatedUser:
    """
    Stub auth dependency used when Entra ID is not yet configured.

    In local development this returns a synthetic user so every endpoint
    remains reachable without a real token. This stub is replaced by
    _entra_auth once Entra is configured.
    """
    logger.debug("Auth stub active — returning synthetic local user")
    return AuthenticatedUser(
        user_id="local-dev-user",
        email="dev@radia.local",
        roles=["admin"],
        display_name="Local Dev User",
    )


async def _entra_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: AppSettings = Depends(get_settings),
) -> AuthenticatedUser:
    """
    Validate a Microsoft Entra ID bearer token.

    TODO (Phase 2): Implement full JWT validation using python-jose:
      - Fetch JWKS from https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys
      - Validate signature, expiry, audience, and issuer
      - Extract roles from token claims
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Placeholder — will be replaced with real validation
    raise NotImplementedError("Entra ID token validation not yet implemented")


def get_current_user_dependency(settings: AppSettings) -> Callable:
    """
    Factory that returns the appropriate auth dependency based on configuration.

    Returns the stub when Entra is not configured (local dev),
    and the real validator when Entra is fully configured.
    """
    if settings.entra.is_configured:
        return _entra_auth
    logger.warning(
        "Entra ID not configured — using stub authentication. "
        "Do NOT use this in production."
    )
    return _stub_auth


def require_role(role: str) -> Callable:
    """
    Dependency factory that enforces a specific role on an endpoint.

    Usage:
        @router.post("/admin/...", dependencies=[Depends(require_role("admin"))])
    """

    async def _check_role(user: AuthenticatedUser = Depends(_stub_auth)) -> None:
        if not user.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' is required for this resource",
            )

    return _check_role
