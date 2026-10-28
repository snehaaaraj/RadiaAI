"""Links each signed-in Microsoft user to their own Jama account.

Jama Connect has no OAuth authorization-code ("Sign in with Jama") flow and its
REST API does not accept Microsoft/SAML sessions, so the only way to act *as the
user* is with the user's personal Jama API credentials (Jama profile -> "Set API
Credentials"). The user submits them once; they are verified against Jama
(``/users/current``), optionally matched to the Microsoft identity, encrypted, and
then used for every Jama call that user makes - so Jama itself enforces which
projects they can read and write.

Outside local development there is no fallback to a shared service account.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from app.core.exceptions import (
    JamaAccountMismatchError,
    JamaAccountNotLinkedError,
    JamaCredentialsInvalidError,
    JamaNotConfiguredError,
)
from app.core.logging import get_logger
from radia_ai.features.jama_requirement_reviewer.connectors.jama_client import (
    JamaApiCredentials,
    JamaClient,
    JamaTokenCache,
)
from radia_ai.features.jama_requirement_reviewer.models.jama_models import (
    JamaAccountLinkRequest,
    JamaAccountStatus,
)
from radia_ai.features.jama_requirement_reviewer.services.jama_service import JamaService

if TYPE_CHECKING:
    from app.core.config import AppSettings
    from app.core.security import AuthenticatedUser
    from radia_ai.features.jama_requirement_reviewer.models.jama_models import JamaUserProfile
    from radia_ai.features.jama_requirement_reviewer.repositories.jama_credential_repository import (
        JamaCredentialRepository,
    )

logger = get_logger(__name__)

JamaClientFactory = Callable[[JamaApiCredentials], JamaClient]


class JamaAccountService:
    """Manage a user's Jama link and build Jama services that act as that user."""

    def __init__(
        self,
        settings: AppSettings,
        repository: JamaCredentialRepository | None,
        token_cache: JamaTokenCache,
        shared_service: JamaService | None = None,
        client_factory: JamaClientFactory | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._token_cache = token_cache
        self._shared_service = shared_service
        self._client_factory = client_factory or (
            lambda credentials: JamaClient(settings.jama, credentials, token_cache)
        )

    @property
    def linking_enabled(self) -> bool:
        return self._repository is not None and self._settings.jama.has_base_url

    def _shared_allowed(self) -> bool:
        return self._settings.allows_shared_jama_account and self._shared_service is not None

    def _require_linking(self) -> JamaCredentialRepository:
        if not self._settings.jama.has_base_url:
            raise JamaNotConfiguredError(
                "Jama integration is not configured. Set JAMA_BASE_URL on the server."
            )
        if self._repository is None:
            raise JamaNotConfiguredError(
                "Jama account linking is not enabled on the server "
                "(JAMA_CREDENTIAL_ENCRYPTION_KEY is not set)."
            )
        return self._repository

    # -- status / link / unlink ---------------------------------------------

    def status(self, user: AuthenticatedUser) -> JamaAccountStatus:
        base_url = self._settings.jama.base_url or None
        link, credentials = (
            self._repository.get_link_and_credentials(user.subject_key)  # type: ignore[union-attr]
            if self.linking_enabled
            else (None, None)
        )
        if link is not None and credentials is not None:
            return JamaAccountStatus(
                linking_enabled=True,
                linked=True,
                jama_base_url=base_url,
                jama_user_id=link.jama_user_id,
                jama_username=link.jama_username,
                jama_email=link.jama_email,
                jama_display_name=link.jama_display_name,
                linked_at=link.linked_at,
            )
        return JamaAccountStatus(
            linking_enabled=self.linking_enabled,
            linked=False,
            relink_required=link is not None,
            using_shared_account=self._shared_allowed(),
            jama_base_url=base_url,
        )

    def link(self, user: AuthenticatedUser, body: JamaAccountLinkRequest) -> JamaAccountStatus:
        repository = self._require_linking()
        credentials = JamaApiCredentials(
            client_id=body.client_id.strip(),
            client_secret=body.client_secret.get_secret_value().strip(),
        )
        client = self._client_factory(credentials)
        try:
            profile = client.get_current_user()
        except JamaCredentialsInvalidError as exc:
            raise JamaCredentialsInvalidError(
                "Jama rejected these API credentials. Check the client ID and secret from your "
                "Jama profile (Set API Credentials) and try again."
            ) from exc

        if not profile.active:
            raise JamaCredentialsInvalidError("This Jama account is deactivated.")
        self._ensure_same_person(user, profile)

        repository.save(user.subject_key, credentials, profile)
        logger.info("jama_account_linked", jama_user_id=profile.id)
        return self.status(user)

    def unlink(self, user: AuthenticatedUser) -> JamaAccountStatus:
        repository = self._require_linking()
        if repository.delete(user.subject_key):
            logger.info("jama_account_unlinked")
        return self.status(user)

    def _ensure_same_person(self, user: AuthenticatedUser, profile: JamaUserProfile) -> None:
        if not self._settings.jama.require_email_match or user.auth_method != "entra":
            return
        jama_names = {
            name.strip().casefold() for name in (profile.email, profile.username) if name.strip()
        }
        if jama_names.isdisjoint(user.identity_names):
            logger.warning("jama_account_link_mismatch", jama_user_id=profile.id)
            raise JamaAccountMismatchError(
                "These Jama credentials belong to a different person. Link the Jama account "
                "whose email matches your Microsoft sign-in.",
                detail={"jama_email": profile.email},
            )

    # -- per-user Jama access -----------------------------------------------

    def credentials_for(self, user: AuthenticatedUser) -> JamaApiCredentials | None:
        """Return ``user``'s own linked Jama OAuth credentials, if any.

        Used by the MCP chat integration to forward a user's own identity to
        mcp-radia so Jama enforces that user's permissions, rather than the
        permissions of a shared service account. Returns ``None`` when the
        user has no personal link - callers should fall back to not
        forwarding any identity (mcp-radia then uses its own configured
        shared credential, if any) rather than substituting one here.
        """
        if not self.linking_enabled:
            return None
        _, credentials = self._repository.get_link_and_credentials(  # type: ignore[union-attr]
            user.subject_key
        )
        return credentials

    def service_for(self, user: AuthenticatedUser) -> JamaService:
        """Return a Jama service acting as ``user``'s linked Jama account."""
        link = None
        if self.linking_enabled:
            link, credentials = self._repository.get_link_and_credentials(  # type: ignore[union-attr]
                user.subject_key
            )
            if credentials is not None:
                return JamaService(self._client_factory(credentials))

        if self._shared_allowed():
            return self._shared_service  # type: ignore[return-value]

        self._require_linking()
        if link is not None:
            raise JamaCredentialsInvalidError(
                "Your saved Jama link can no longer be used. Re-link your Jama account in "
                "Settings to browse Jama.",
            )
        raise JamaAccountNotLinkedError(
            "Link your Jama account to browse Jama. Radia then only shows the projects and "
            "items your own Jama account can access.",
        )
