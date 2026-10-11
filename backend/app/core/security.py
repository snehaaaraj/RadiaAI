"""
Authentication and authorization for Microsoft Entra ID.

Every protected endpoint depends on :func:`get_current_user` (directly or through
one of the role dependencies below). It validates the caller's Entra ID access
token - RS256 signature against the tenant's published signing keys, issuer,
audience, expiry/not-before, tenant, delegated scope - and maps the token to an
:class:`AuthenticatedUser` carrying the user's Radia app roles.

When Entra ID is not configured a synthetic user is returned, but only for the
``local`` and ``test`` environments. Any other environment fails closed.

Roles are Entra *app roles* defined on the API app registration and assigned to
users or groups in Enterprise Applications:

  - ``Radia.User``           use the app: chat, search, standards, reviews, Jama
  - ``Radia.Admin``          everything, including document management and all users' review history
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

import httpx
import jwt
import structlog
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import AppSettings, EntraIDSettings, get_settings
from app.core.exceptions import (
    AuthenticationError,
    AuthenticationNotConfiguredError,
    AuthorizationError,
    RadiaBaseException,
)
from app.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

logger = get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False, description="Microsoft Entra ID access token")

_ALLOWED_ALGORITHMS = ["RS256"]
# Never refetch signing keys more often than this when an unknown 'kid' arrives,
# so a flood of forged tokens cannot turn into a flood of requests to Entra.
_MIN_JWKS_REFRESH_INTERVAL_SECONDS = 300.0


class Role(StrEnum):
    """Radia app roles (the ``value`` of each app role on the API app registration)."""

    USER = "Radia.User"
    ADMIN = "Radia.Admin"


_ROLE_IMPLICATIONS: dict[str, frozenset[str]] = {
    Role.ADMIN: frozenset({Role.ADMIN, Role.USER}),
    Role.USER: frozenset({Role.USER}),
}


def expand_roles(roles: Iterable[str]) -> frozenset[str]:
    """Return the granted roles plus every role they imply."""
    effective: set[str] = set()
    for role in roles:
        effective |= _ROLE_IMPLICATIONS.get(role, frozenset({role}))
    return frozenset(effective)


class AuthProviderUnavailableError(RadiaBaseException):
    """Raised when Entra signing keys cannot be fetched and none are cached."""

    http_status = HTTPStatus.SERVICE_UNAVAILABLE
    error_code = "AUTH_PROVIDER_UNAVAILABLE"


@dataclass(frozen=True)
class AuthenticatedUser:
    """A verified caller after token validation."""

    user_id: str
    email: str
    roles: frozenset[str]
    display_name: str = ""
    tenant_id: str = ""
    auth_method: Literal["entra", "local"] = "entra"
    is_app: bool = False
    identity_aliases: frozenset[str] = frozenset()
    effective_roles: frozenset[str] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "roles", frozenset(self.roles))
        object.__setattr__(self, "effective_roles", expand_roles(self.roles))

    def has_role(self, role: str) -> bool:
        return role in self.effective_roles

    @property
    def is_admin(self) -> bool:
        return self.has_role(Role.ADMIN)

    @property
    def subject_key(self) -> str:
        """Stable, tenant-qualified identity used to key per-user data."""
        return f"{self.tenant_id}:{self.user_id}"

    @property
    def identity_names(self) -> frozenset[str]:
        """Lower-cased email/UPN values used to match external accounts to this user."""
        names = {self.email, *self.identity_aliases}
        return frozenset(name.strip().casefold() for name in names if name and name.strip())

    @classmethod
    def from_claims(cls, claims: dict[str, Any]) -> AuthenticatedUser:
        name_claims = ("email", "preferred_username", "upn", "unique_name")
        names = [str(claims[key]) for key in name_claims if claims.get(key)]
        email = names[0] if names else ""
        raw_roles = claims.get("roles") or []
        roles = (
            frozenset(str(role) for role in raw_roles)
            if isinstance(raw_roles, list)
            else frozenset()
        )
        return cls(
            user_id=str(claims["oid"]),
            tenant_id=str(claims["tid"]),
            email=email,
            display_name=str(claims.get("name") or email),
            roles=roles,
            auth_method="entra",
            is_app="scp" not in claims,
            identity_aliases=frozenset(names),
        )


def local_dev_user(settings: AppSettings) -> AuthenticatedUser:
    """Synthetic user for local development and tests when Entra is not configured."""
    return AuthenticatedUser(
        user_id="local-dev-user",
        tenant_id="local",
        email="dev@radia.local",
        display_name="Local Dev User",
        roles=frozenset(settings.local_dev_user_roles),
        auth_method="local",
    )


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------


def _fetch_jwks(settings: EntraIDSettings) -> dict[str, Any]:
    response = httpx.get(settings.jwks_url, timeout=settings.http_timeout_seconds)
    response.raise_for_status()
    return cast(dict[str, Any], response.json())


class _SigningKeyCache:
    """Thread-safe cache of the tenant's signing keys, refreshed on TTL or key rotation."""

    def __init__(
        self,
        fetch: Callable[[], dict[str, Any]],
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch = fetch
        self._ttl = ttl_seconds
        self._clock = clock
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float | None = None
        self._lock = threading.Lock()

    def get(self, kid: str) -> jwt.PyJWK:
        with self._lock:
            now = self._clock()
            age = None if self._fetched_at is None else now - self._fetched_at
            expired = age is None or age >= self._ttl
            if kid in self._keys and not expired:
                return self._keys[kid]
            # Unknown kid usually means Entra rotated keys; refresh, but rate-limited.
            if expired or age is None or age >= _MIN_JWKS_REFRESH_INTERVAL_SECONDS:
                self._refresh(now)
            key = self._keys.get(kid)
        if key is None:
            raise jwt.InvalidTokenError("Token signing key is not trusted")
        return key

    def _refresh(self, now: float) -> None:
        try:
            document = self._fetch()
        except Exception as exc:
            if self._keys:
                # Keep serving with the last known keys rather than locking every user out.
                logger.warning("entra_jwks_refresh_failed_using_cached_keys", error=str(exc))
                self._fetched_at = now
                return
            logger.exception("entra_jwks_fetch_failed")
            raise AuthProviderUnavailableError(
                "Unable to reach Microsoft Entra ID to verify the sign-in. Please retry shortly."
            ) from exc

        keys: dict[str, jwt.PyJWK] = {}
        for raw in document.get("keys", []):
            if not isinstance(raw, dict) or raw.get("kty") != "RSA" or not raw.get("kid"):
                continue
            if raw.get("use") not in (None, "sig"):
                continue
            try:
                keys[str(raw["kid"])] = jwt.PyJWK(raw, algorithm="RS256")
            except jwt.PyJWTError:
                logger.warning("entra_jwks_key_skipped", kid=raw.get("kid"))
        if not keys:
            raise AuthProviderUnavailableError(
                "Microsoft Entra ID returned no usable signing keys."
            )
        self._keys = keys
        self._fetched_at = now
        logger.info("entra_jwks_refreshed", key_count=len(keys))


class EntraTokenValidator:
    """Validates Microsoft Entra ID access tokens issued for the Radia API."""

    def __init__(
        self,
        settings: EntraIDSettings,
        *,
        jwks_fetcher: Callable[[], dict[str, Any]] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings
        self._keys = _SigningKeyCache(
            jwks_fetcher or (lambda: _fetch_jwks(settings)),
            ttl_seconds=settings.jwks_cache_ttl_seconds,
            clock=clock,
        )

    def validate(self, token: str) -> dict[str, Any]:
        """Return verified claims, or raise ``jwt.InvalidTokenError``."""
        header = jwt.get_unverified_header(token)
        if header.get("alg") not in _ALLOWED_ALGORITHMS:
            raise jwt.InvalidAlgorithmError("Token algorithm is not allowed")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise jwt.InvalidTokenError("Token has no key id")

        signing_key = self._keys.get(kid)
        claims = jwt.decode(
            token,
            key=signing_key.key,
            algorithms=_ALLOWED_ALGORITHMS,
            audience=self.settings.accepted_audiences,
            issuer=self.settings.accepted_issuers,
            leeway=self.settings.clock_skew_seconds,
            options={"require": ["exp", "iat", "iss", "aud", "tid", "oid"]},
        )

        if str(claims["tid"]).casefold() != self.settings.tenant_id.strip().casefold():
            raise jwt.InvalidTokenError("Token was issued for a different tenant")

        scopes = str(claims.get("scp") or "").split()
        if "scp" in claims and self.settings.required_scope not in scopes:
            raise jwt.InvalidTokenError("Token does not carry the required API scope")
        return claims


def get_token_validator(request: Request, settings: EntraIDSettings) -> EntraTokenValidator:
    """Return the app-wide validator so signing keys are cached across requests."""
    validator = getattr(request.app.state, "entra_token_validator", None)
    if not isinstance(validator, EntraTokenValidator) or validator.settings != settings:
        validator = EntraTokenValidator(settings)
        request.app.state.entra_token_validator = validator
    return validator


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: AppSettings = Depends(get_settings),
) -> AuthenticatedUser:
    """
    Authenticate the caller and return the verified user.

    Declared as a sync dependency so the (rare) blocking signing-key fetch runs in
    the threadpool instead of on the event loop.
    """
    if not settings.entra.is_configured:
        if settings.allows_local_auth_bypass:
            return _bind_user(request, local_dev_user(settings))
        raise AuthenticationNotConfiguredError(
            "Authentication is not configured for this deployment. Contact an administrator."
        )

    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Sign in with your Microsoft account to continue.")

    validator = get_token_validator(request, settings.entra)
    try:
        claims = validator.validate(credentials.credentials)
    except jwt.PyJWTError as exc:
        logger.info("access_token_rejected", reason=type(exc).__name__, detail=str(exc))
        raise AuthenticationError(
            "Your sign-in is invalid or has expired. Please sign in again."
        ) from exc

    user = AuthenticatedUser.from_claims(claims)
    if user.is_app and not settings.entra.allow_app_tokens:
        raise AuthorizationError("Application tokens are not accepted by this API.")
    if user.is_app and not user.roles:
        raise AuthorizationError("Application token carries no Radia roles.")
    if settings.entra.require_app_role and not user.has_role(Role.USER):
        raise AuthorizationError(
            "Your account has not been granted access to Radia AI. Ask an administrator to "
            "assign you a Radia role."
        )
    return _bind_user(request, user)


def _bind_user(request: Request, user: AuthenticatedUser) -> AuthenticatedUser:
    request.state.user = user
    structlog.contextvars.bind_contextvars(user_id=user.user_id, auth_method=user.auth_method)
    return user


def require_roles(*roles: Role) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Build a dependency that admits users holding at least one of ``roles``."""
    required = tuple(roles)

    def dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if not any(user.has_role(role) for role in required):
            logger.info("authorization_denied", required_roles=[str(role) for role in required])
            raise AuthorizationError(
                "You do not have permission to perform this action.",
                detail={"required_roles": [str(role) for role in required]},
            )
        return user

    dependency.__name__ = f"require_{'_or_'.join(role.name.lower() for role in required)}"
    return dependency


require_user = require_roles(Role.USER)
require_admin = require_roles(Role.ADMIN)

CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]
RadiaUserDep = Annotated[AuthenticatedUser, Depends(require_user)]
AdminDep = Annotated[AuthenticatedUser, Depends(require_admin)]
