"""Shared plumbing for the Atlassian Cloud connectors (Jira and Confluence).

On Atlassian Cloud both products live under one site (``https://org.atlassian.net``)
and accept the same credential: an account email plus an API token, sent as HTTP
Basic auth. Jira sits at ``/rest/api/3``; Confluence sits under ``/wiki``.

So Jira and Confluence share one settings class and one HTTP client here, and
each connector module only deals with its own endpoints and payload shapes.
"""

from typing import Any, NoReturn

import httpx2
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_radia.config import ENV_FILE
from mcp_radia.connectors.errors import (
    ConnectorAuthError,
    ConnectorNotConfiguredError,
    ConnectorServiceError,
    ItemNotFoundError,
)
from mcp_radia.logging import get_logger

logger = get_logger(__name__)


class AtlassianSettings(BaseSettings):
    """Atlassian Cloud connection settings, read from ``ATLASSIAN_*`` variables.

    One credential set covers both Jira and Confluence, which is how Atlassian
    Cloud API tokens work: the token is scoped to the user account, and the
    account's product permissions decide what it can read.
    """

    model_config = SettingsConfigDict(env_prefix="ATLASSIAN_", env_file=ENV_FILE, extra="ignore")

    site_url: str = Field(
        default="",
        description="Cloud site root, e.g. https://yourorg.atlassian.net (no trailing path).",
    )
    email: str = Field(default="", description="Atlassian account email that owns the API token.")
    api_token: str = Field(
        default="",
        description="API token from id.atlassian.com/manage-profile/security/api-tokens.",
    )
    timeout_seconds: float = Field(default=20.0, gt=0, description="Per-request timeout.")
    verify_ssl: bool = Field(default=True, description="Verify TLS certificates.")

    @property
    def base(self) -> str:
        """Site root with any trailing slash removed."""
        return self.site_url.rstrip("/")

    @property
    def is_configured(self) -> bool:
        """True only when a site and a complete credential pair are present."""
        return bool(self.site_url and self.email and self.api_token)


class AtlassianClient:
    """Base async client for Atlassian Cloud REST APIs.

    Subclasses set :attr:`system` and build paths relative to the site root.
    """

    #: Name used in error messages and logs; overridden by each product.
    system = "atlassian"

    #: Human-readable name of the env var block an operator must fill in.
    config_hint = "ATLASSIAN_SITE_URL, ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN"

    def __init__(
        self, settings: AtlassianSettings, *, client: httpx2.AsyncClient | None = None
    ) -> None:
        """Create a client.

        Args:
            settings: Shared Atlassian Cloud settings.
            client: An HTTP client to use instead of one of our own. Tests pass
                an ``AsyncClient`` backed by ``httpx2.MockTransport``.
        """
        self._settings = settings
        self._client = client
        self._owns_client = client is None

    @property
    def settings(self) -> AtlassianSettings:
        return self._settings

    @property
    def is_configured(self) -> bool:
        return self._settings.is_configured

    async def aclose(self) -> None:
        """Close the underlying HTTP client, if this connector owns it."""
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    # -- plumbing -----------------------------------------------------------

    def _ensure_configured(self) -> None:
        if not self._settings.is_configured:
            raise ConnectorNotConfiguredError(
                f"{self.system.title()} is not configured. Set {self.config_hint} "
                "in mcp-radia/.env.",
                system=self.system,
            )

    def _get_client(self) -> httpx2.AsyncClient:
        if self._client is None:
            self._client = httpx2.AsyncClient(
                verify=self._settings.verify_ssl,
                timeout=self._settings.timeout_seconds,
            )
        return self._client

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET ``{site}/{path}`` with Basic auth and return the parsed JSON object."""
        self._ensure_configured()
        client = self._get_client()
        url = f"{self._settings.base}/{path.lstrip('/')}"
        auth = httpx2.BasicAuth(self._settings.email, self._settings.api_token)

        try:
            response = await client.get(
                url,
                params=params,
                headers={"Accept": "application/json"},
                auth=auth,
            )
            response.raise_for_status()
        except httpx2.HTTPStatusError as exc:
            self._raise_for_status(exc, path)
        except httpx2.HTTPError as exc:
            raise ConnectorServiceError(
                f"Could not reach the {self.system.title()} API.",
                system=self.system,
                operation=path,
                detail={"error": str(exc)},
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ConnectorServiceError(
                f"{self.system.title()} returned a response that was not valid JSON.",
                system=self.system,
                operation=path,
            ) from exc

        if not isinstance(payload, dict):
            raise ConnectorServiceError(
                f"{self.system.title()} returned an unexpected payload shape "
                "(expected a JSON object).",
                system=self.system,
                operation=path,
            )
        return payload

    def _raise_for_status(self, exc: httpx2.HTTPStatusError, path: str) -> NoReturn:
        """Translate an HTTP error status into the right connector exception."""
        status = exc.response.status_code
        if status in (401, 403):
            raise ConnectorAuthError(
                f"{self.system.title()} rejected the request. Check {self.config_hint}, and "
                "that the account has permission to read this resource.",
                system=self.system,
                operation=path,
                status_code=status,
            ) from exc
        if status == 404:
            raise ItemNotFoundError(
                f"The requested {self.system.title()} resource was not found.",
                system=self.system,
                operation=path,
                status_code=status,
            ) from exc
        if status == 429:
            # Atlassian Cloud rate-limits aggressively; say so plainly rather
            # than reporting a generic server error.
            raise ConnectorServiceError(
                f"{self.system.title()} rate-limited this request. Retry after a short wait.",
                system=self.system,
                operation=path,
                status_code=status,
            ) from exc
        raise ConnectorServiceError(
            f"The {self.system.title()} API returned an error response.",
            system=self.system,
            operation=path,
            status_code=status,
        ) from exc
