"""Jama Connect REST API connector (read-only).

A fresh, async implementation written against the Jama REST API directly. It
deliberately shares no code with the RadiaAI backend's
``jama_requirement_reviewer`` feature: patterns there were read for inspiration,
but importing across the two packages would couple services that are meant to
deploy independently.

Two authentication modes are supported, matching how Jama is actually reached:

  - ``basic`` - HTTP Basic auth with a username/password or a Jama Cloud
    API ID / API key pair.
  - ``oauth`` - OAuth 2.0 client-credentials against ``/rest/oauth/token``;
    the bearer token is cached until shortly before it expires.

Read operations only:

  - :meth:`JamaClient.get_item`  -> GET /rest/{version}/items/{id}
  - :meth:`JamaClient.search`    -> GET /rest/{version}/abstractitems
"""

import asyncio
import time
from typing import Any, Literal

import httpx2
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_radia.config import ENV_FILE
from mcp_radia.connectors.errors import (
    ConnectorAuthError,
    ConnectorNotConfiguredError,
    ConnectorServiceError,
    ItemNotFoundError,
)
from mcp_radia.connectors.text import strip_html
from mcp_radia.logging import get_logger

logger = get_logger(__name__)

SYSTEM = "jama"

# Refresh OAuth tokens this many seconds before their stated expiry, so a token
# cannot expire in flight between the check and the request.
_TOKEN_EXPIRY_SKEW_SECONDS = 60

# Jama caps page size at 50 on most collection endpoints; asking for more errors.
MAX_PAGE_SIZE = 50

# Re-exported so callers can keep importing it from the connector they use.
__all__ = [
    "MAX_PAGE_SIZE",
    "JamaClient",
    "JamaItem",
    "JamaSearchResult",
    "JamaSettings",
    "strip_html",
]


class JamaSettings(BaseSettings):
    """Jama Connect connection settings, read from ``JAMA_*`` environment variables."""

    model_config = SettingsConfigDict(env_prefix="JAMA_", env_file=ENV_FILE, extra="ignore")

    base_url: str = Field(
        default="",
        description="Instance root URL, e.g. https://yourorg.jamacloud.com (no /rest suffix).",
    )
    auth_type: Literal["basic", "oauth"] = Field(
        default="basic", description="Authentication mode."
    )
    username: str = Field(default="", description="Username or API ID (basic auth).")
    password: str = Field(default="", description="Password or API key (basic auth).")
    client_id: str = Field(default="", description="OAuth client ID (client-credentials).")
    client_secret: str = Field(default="", description="OAuth client secret (client-credentials).")
    api_version: str = Field(default="v1", description="REST API version path segment.")
    timeout_seconds: float = Field(default=20.0, gt=0, description="Per-request timeout.")
    verify_ssl: bool = Field(
        default=True, description="Verify TLS certificates. Disable only for self-hosted test."
    )

    @property
    def rest_base(self) -> str:
        """Fully-qualified REST base, e.g. ``https://org.jamacloud.com/rest/v1``."""
        return f"{self.base_url.rstrip('/')}/rest/{self.api_version.strip('/')}"

    @property
    def token_url(self) -> str:
        """OAuth client-credentials token endpoint."""
        return f"{self.base_url.rstrip('/')}/rest/oauth/token"

    @property
    def is_configured(self) -> bool:
        """True only with a base URL *and* a complete credential set for the chosen mode."""
        if not self.base_url:
            return False
        if self.auth_type == "oauth":
            return bool(self.client_id and self.client_secret)
        return bool(self.username and self.password)


class JamaItemSummary(BaseModel):
    """A single row in a Jama search result."""

    id: int = Field(description="Numeric Jama item id.")
    document_key: str | None = Field(default=None, description="Human-readable key, e.g. SRS-42.")
    global_id: str | None = Field(default=None, description="Global id, stable across projects.")
    name: str = Field(default="", description="Item name / title.")
    item_type_id: int | None = Field(default=None, description="Numeric item type id.")
    project_id: int | None = Field(default=None, description="Owning project id.")
    web_url: str | None = Field(default=None, description="Browser URL for a human to open.")


class JamaItem(BaseModel):
    """A full Jama item."""

    id: int = Field(description="Numeric Jama item id.")
    document_key: str | None = Field(default=None, description="Human-readable key, e.g. SRS-42.")
    global_id: str | None = Field(default=None, description="Global id, stable across projects.")
    name: str = Field(default="", description="Item name / title.")
    description: str = Field(default="", description="Description, converted from HTML to text.")
    status: str | None = Field(default=None, description="Workflow status, if the type has one.")
    item_type_id: int | None = Field(default=None, description="Numeric item type id.")
    project_id: int | None = Field(default=None, description="Owning project id.")
    created_date: str | None = Field(default=None, description="ISO 8601 creation timestamp.")
    modified_date: str | None = Field(default=None, description="ISO 8601 last-modified timestamp.")
    web_url: str | None = Field(default=None, description="Browser URL for a human to open.")
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw Jama field map, including any custom fields on the item type.",
    )


class JamaSearchResult(BaseModel):
    """A page of Jama search results."""

    results: list[JamaItemSummary] = Field(default_factory=list, description="Items on this page.")
    total: int = Field(default=0, description="Total matches across all pages.")
    start_at: int = Field(default=0, description="Zero-based index of the first item returned.")
    max_results: int = Field(default=0, description="Page size actually applied.")


class JamaClient:
    """Async, read-only client over the Jama Connect REST API."""

    def __init__(self, settings: JamaSettings, *, client: httpx2.AsyncClient | None = None) -> None:
        """Create a client.

        Args:
            settings: Connection settings.
            client: An HTTP client to use instead of one of our own. Tests pass
                an ``AsyncClient`` backed by ``httpx2.MockTransport``; when
                omitted the connector creates and owns a client lazily.
        """
        self._settings = settings
        self._client = client
        self._owns_client = client is None
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        # Guards the token refresh so concurrent tool calls make one token
        # request, not one each.
        self._token_lock = asyncio.Lock()

    @property
    def settings(self) -> JamaSettings:
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
                "Jama is not configured. Set JAMA_BASE_URL and the credentials for the "
                f"{self._settings.auth_type} auth mode in mcp-radia/.env.",
                system=SYSTEM,
            )

    def _get_client(self) -> httpx2.AsyncClient:
        if self._client is None:
            self._client = httpx2.AsyncClient(
                verify=self._settings.verify_ssl,
                timeout=self._settings.timeout_seconds,
            )
        return self._client

    async def _fetch_token(self, client: httpx2.AsyncClient) -> str:
        """Exchange client credentials for a bearer token."""
        try:
            response = await client.post(
                self._settings.token_url,
                data={"grant_type": "client_credentials"},
                auth=httpx2.BasicAuth(self._settings.client_id, self._settings.client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
        except httpx2.HTTPStatusError as exc:
            raise ConnectorAuthError(
                "Jama rejected the OAuth token request. Check JAMA_CLIENT_ID and "
                "JAMA_CLIENT_SECRET.",
                system=SYSTEM,
                operation="oauth_token",
                status_code=exc.response.status_code,
            ) from exc
        except httpx2.HTTPError as exc:
            raise ConnectorServiceError(
                "Could not reach the Jama OAuth token endpoint.",
                system=SYSTEM,
                operation="oauth_token",
                detail={"error": str(exc)},
            ) from exc

        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ConnectorServiceError(
                "Jama OAuth response contained no access_token.",
                system=SYSTEM,
                operation="oauth_token",
            )
        expires_in = float(payload.get("expires_in", 3600))
        self._token = str(token)
        self._token_expires_at = time.monotonic() + expires_in - _TOKEN_EXPIRY_SKEW_SECONDS
        logger.debug("jama_oauth_token_refreshed", expires_in=expires_in)
        return self._token

    async def _bearer_token(self, client: httpx2.AsyncClient) -> str:
        async with self._token_lock:
            if self._token is None or time.monotonic() >= self._token_expires_at:
                return await self._fetch_token(client)
            return self._token

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform an authenticated GET against the REST base and return parsed JSON."""
        self._ensure_configured()
        client = self._get_client()
        url = f"{self._settings.rest_base}/{path.lstrip('/')}"

        headers = {"Accept": "application/json"}
        auth: httpx2.BasicAuth | None = None
        if self._settings.auth_type == "oauth":
            headers["Authorization"] = f"Bearer {await self._bearer_token(client)}"
        else:
            auth = httpx2.BasicAuth(self._settings.username, self._settings.password)

        try:
            response = await client.get(url, params=params, headers=headers, auth=auth)
            response.raise_for_status()
        except httpx2.HTTPStatusError as exc:
            self._raise_for_status(exc, path)
        except httpx2.HTTPError as exc:
            raise ConnectorServiceError(
                "Could not reach the Jama API.",
                system=SYSTEM,
                operation=path,
                detail={"error": str(exc)},
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ConnectorServiceError(
                "Jama returned a response that was not valid JSON.",
                system=SYSTEM,
                operation=path,
            ) from exc

        if not isinstance(payload, dict):
            raise ConnectorServiceError(
                "Jama returned an unexpected payload shape (expected a JSON object).",
                system=SYSTEM,
                operation=path,
            )
        return payload

    @staticmethod
    def _raise_for_status(exc: httpx2.HTTPStatusError, path: str) -> None:
        """Translate an HTTP error status into the right connector exception."""
        status = exc.response.status_code
        if status == 404:
            raise ItemNotFoundError(
                "The requested Jama resource was not found.",
                system=SYSTEM,
                operation=path,
                status_code=status,
            ) from exc
        if status in (401, 403):
            raise ConnectorAuthError(
                "Jama rejected the request. Check the configured credentials and that the "
                "account has permission to read this item.",
                system=SYSTEM,
                operation=path,
                status_code=status,
            ) from exc
        raise ConnectorServiceError(
            "The Jama API returned an error response.",
            system=SYSTEM,
            operation=path,
            status_code=status,
        ) from exc

    # -- mapping ------------------------------------------------------------

    def _web_url(self, item_id: int, project_id: int | None) -> str | None:
        base = self._settings.base_url.rstrip("/")
        if not base:
            return None
        if project_id is None:
            return f"{base}/perspective.req#/items/{item_id}"
        return f"{base}/perspective.req#/items/{item_id}?projectId={project_id}"

    def _summary_from_raw(self, raw: dict[str, Any]) -> JamaItemSummary:
        fields = raw.get("fields") or {}
        item_id = int(raw["id"])
        project_id = raw.get("project")
        return JamaItemSummary(
            id=item_id,
            document_key=raw.get("documentKey"),
            global_id=raw.get("globalId"),
            name=str(fields.get("name") or ""),
            item_type_id=raw.get("itemType"),
            project_id=project_id,
            web_url=self._web_url(item_id, project_id),
        )

    def _item_from_raw(self, raw: dict[str, Any]) -> JamaItem:
        fields: dict[str, Any] = raw.get("fields") or {}
        status = fields.get("status")
        item_id = int(raw["id"])
        project_id = raw.get("project")
        return JamaItem(
            id=item_id,
            document_key=raw.get("documentKey"),
            global_id=raw.get("globalId"),
            name=str(fields.get("name") or ""),
            description=strip_html(fields.get("description")),
            status=str(status) if status is not None else None,
            item_type_id=raw.get("itemType"),
            project_id=project_id,
            created_date=raw.get("createdDate"),
            modified_date=raw.get("modifiedDate"),
            web_url=self._web_url(item_id, project_id),
            fields=fields,
        )

    # -- public API ---------------------------------------------------------

    async def get_item(self, item_id: int) -> JamaItem:
        """Read a single Jama item by its numeric id."""
        payload = await self._get(f"items/{item_id}")
        data = payload.get("data")
        if not isinstance(data, dict) or not data:
            raise ItemNotFoundError(
                f"Jama item {item_id} was not found.",
                system=SYSTEM,
                operation=f"items/{item_id}",
                detail={"item_id": item_id},
            )
        item = self._item_from_raw(data)
        logger.info("jama_item_fetched", item_id=item_id, document_key=item.document_key)
        return item

    async def search(
        self,
        *,
        query: str | None = None,
        project_id: int | None = None,
        item_type_id: int | None = None,
        start_at: int = 0,
        max_results: int = MAX_PAGE_SIZE,
    ) -> JamaSearchResult:
        """Search items, optionally scoped by project, type and free text."""
        capped = max(1, min(max_results, MAX_PAGE_SIZE))
        params: dict[str, Any] = {"startAt": max(0, start_at), "maxResults": capped}
        if query:
            params["contains"] = query
        if project_id is not None:
            params["project"] = project_id
        if item_type_id is not None:
            params["itemType"] = item_type_id

        payload = await self._get("abstractitems", params=params)
        raw_items = payload.get("data") or []
        if not isinstance(raw_items, list):
            raise ConnectorServiceError(
                "Jama search returned an unexpected 'data' shape (expected a list).",
                system=SYSTEM,
                operation="abstractitems",
            )

        page_info = (payload.get("meta") or {}).get("pageInfo") or {}
        results = [self._summary_from_raw(item) for item in raw_items]
        logger.info("jama_search_completed", query=query, returned=len(results))
        return JamaSearchResult(
            results=results,
            total=int(page_info.get("totalResults", len(results))),
            start_at=int(page_info.get("startIndex", start_at)),
            max_results=capped,
        )
