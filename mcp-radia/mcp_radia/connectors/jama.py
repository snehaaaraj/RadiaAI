"""Jama Connect REST API connector (read-only).

A fresh, async implementation written against the Jama REST API directly. It
deliberately shares no code with the RadiaAI backend's
``jama_requirement_reviewer`` feature: patterns there were read for inspiration,
but importing across the two packages would couple services that are meant to
deploy independently.

Authentication is OAuth 2.0 client-credentials against ``/rest/oauth/token``
only, and always as an individual user: there is no shared server account.
Connection settings (:class:`JamaSettings`) and identity
(:class:`JamaCredentials`) are kept apart so the server can own the former
while each caller supplies the latter:

  - Streamable HTTP: the RadiaAI backend forwards the signed-in user's linked
    Jama OAuth client on every request (see :mod:`mcp_radia.tools._identity`).
  - stdio: a person running the server locally (GitHub Copilot, Claude
    Desktop) sets their *own* Jama OAuth client in ``JAMA_CLIENT_ID`` /
    ``JAMA_CLIENT_SECRET``, read by :class:`JamaLocalCredentials`.

The bearer token is cached until shortly before it expires.

Read operations only:

  - :meth:`JamaClient.get_item`      -> GET /rest/{version}/items/{id}
  - :meth:`JamaClient.search`        -> GET /rest/{version}/abstractitems
  - :meth:`JamaClient.get_children`  -> GET /rest/{version}/items/{id}/children
  - :meth:`JamaClient.list_projects` -> GET /rest/{version}/projects
"""

import asyncio
import time
from typing import Any

import httpx2
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_radia.config import ENV_FILE
from mcp_radia.connectors.errors import (
    ConnectorAuthError,
    ConnectorNotConfiguredError,
    ConnectorServiceError,
    ItemNotFoundError,
    extract_remote_message,
)
from mcp_radia.connectors.retry import get_with_retry
from mcp_radia.connectors.text import strip_html
from mcp_radia.logging import get_logger

logger = get_logger(__name__)

SYSTEM = "jama"

# Refresh OAuth tokens this many seconds before their stated expiry, so a token
# cannot expire in flight between the check and the request.
_TOKEN_EXPIRY_SKEW_SECONDS = 60

# Jama caps page size at 50 on most collection endpoints; asking for more errors.
MAX_PAGE_SIZE = 50

# Jama repeats these inside the raw ``fields`` map, but each is already
# surfaced as a typed attribute on JamaItem - and ``description`` is repeated as
# raw HTML, which measured ~75% of a single item's payload on a real instance.
# Dropping them removes duplication only; nothing here is otherwise unavailable.
_FIELDS_SURFACED_ELSEWHERE = frozenset({"name", "description", "status"})

# Re-exported so callers can keep importing it from the connector they use.
__all__ = [
    "MAX_PAGE_SIZE",
    "JamaChildrenResult",
    "JamaClient",
    "JamaCredentials",
    "JamaItem",
    "JamaLocalCredentials",
    "JamaProjectSummary",
    "JamaSearchResult",
    "JamaSettings",
    "strip_html",
]


class JamaSettings(BaseSettings):
    """Jama Connect connection settings, read from ``JAMA_*`` environment variables.

    Deliberately carries no credentials: who the call runs as is supplied
    separately, per caller, as :class:`JamaCredentials`.
    """

    model_config = SettingsConfigDict(env_prefix="JAMA_", env_file=ENV_FILE, extra="ignore")

    base_url: str = Field(
        default="",
        description="Instance root URL, e.g. https://yourorg.jamacloud.com (no /rest suffix).",
    )
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
        """True when the server knows which Jama instance to reach."""
        return bool(self.base_url)


class JamaCredentials(BaseModel):
    """One individual's Jama OAuth client-credentials pair."""

    client_id: str = Field(description="OAuth client ID (client-credentials).")
    client_secret: str = Field(repr=False, description="OAuth client secret (client-credentials).")

    @property
    def is_complete(self) -> bool:
        return bool(self.client_id.strip() and self.client_secret.strip())


class JamaLocalCredentials(BaseSettings):
    """The local user's *own* Jama OAuth client, for stdio use only.

    Read from ``JAMA_CLIENT_ID`` / ``JAMA_CLIENT_SECRET``. Only the stdio
    entry point loads this; the HTTP transport never does, so a deployed
    server cannot act as anyone other than the user whose headers arrive.
    """

    model_config = SettingsConfigDict(env_prefix="JAMA_", env_file=ENV_FILE, extra="ignore")

    client_id: str = Field(default="", description="Your Jama OAuth client ID.")
    client_secret: str = Field(default="", repr=False, description="Your Jama OAuth client secret.")

    def to_credentials(self) -> JamaCredentials | None:
        """The credentials, or ``None`` when either half is unset."""
        credentials = JamaCredentials(client_id=self.client_id, client_secret=self.client_secret)
        return credentials if credentials.is_complete else None


class JamaItemSummary(BaseModel):
    """A single row in a Jama search result."""

    id: int = Field(description="Numeric Jama item id.")
    document_key: str | None = Field(default=None, description="Human-readable key, e.g. SRS-42.")
    global_id: str | None = Field(default=None, description="Global id, stable across projects.")
    name: str = Field(default="", description="Item name / title.")
    item_type_id: int | None = Field(default=None, description="Numeric item type id.")
    project_id: int | None = Field(default=None, description="Owning project id.")
    parent_id: int | None = Field(
        default=None,
        description=(
            "Numeric id of this item's container (document-tree) parent, from Jama's "
            "location.parent.item - the 'what sits above this in the tree' relationship. "
            "Distinct from a traceability relationship (list_related_items) and from "
            "containment children (jama_get_children). None for a top-level item."
        ),
    )
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
    parent_id: int | None = Field(
        default=None,
        description=(
            "Numeric id of this item's container (document-tree) parent, from Jama's "
            "location.parent.item - the 'what sits above this in the tree' relationship. "
            "Distinct from a traceability relationship (list_related_items) and from "
            "containment children (jama_get_children). None for a top-level item."
        ),
    )
    created_date: str | None = Field(default=None, description="ISO 8601 creation timestamp.")
    modified_date: str | None = Field(default=None, description="ISO 8601 last-modified timestamp.")
    web_url: str | None = Field(default=None, description="Browser URL for a human to open.")
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Jama's field map, carrying custom fields defined on the item type. "
            "Name, description and status are omitted here because each is already "
            "returned as its own attribute - description in particular is stored as "
            "raw HTML and dominated the payload."
        ),
    )


class JamaProjectSummary(BaseModel):
    """A single row in a Jama project listing.

    Exists so a caller can resolve a project's name/key to its numeric id
    before calling :meth:`JamaClient.search` with ``project_id`` - the same
    "search first, never guess a numeric id" pattern item lookups already
    need (see :meth:`JamaClient.search`).
    """

    id: int = Field(description="Numeric Jama project id.")
    project_key: str | None = Field(default=None, description="Short project key, e.g. SAND.")
    name: str = Field(default="", description="Project display name.")


class JamaRelatedItem(BaseModel):
    """An item related to another through a Jama relationship."""

    direction: str = Field(
        description="'upstream' (this item derives from it) or 'downstream' (derives from this)."
    )
    item: JamaItemSummary = Field(description="The item on the other end.")


class JamaChildrenResult(BaseModel):
    """A page of a Jama item's direct children.

    Containment, not traceability: these are the items nested *inside* the
    parent in the document tree, which is a different axis from the
    upstream/downstream relationships :class:`JamaRelatedItem` carries.
    """

    parent_id: int = Field(description="Numeric id of the item whose children these are.")
    results: list[JamaItemSummary] = Field(
        default_factory=list, description="Direct children on this page."
    )
    total: int = Field(default=0, description="Total direct children across all pages.")
    start_at: int = Field(default=0, description="Zero-based index of the first child returned.")
    max_results: int = Field(default=0, description="Page size actually applied.")


class JamaSearchResult(BaseModel):
    """A page of Jama search results."""

    results: list[JamaItemSummary] = Field(default_factory=list, description="Items on this page.")
    total: int = Field(default=0, description="Total matches across all pages.")
    start_at: int = Field(default=0, description="Zero-based index of the first item returned.")
    max_results: int = Field(default=0, description="Page size actually applied.")


class JamaClient:
    """Async, read-only client over the Jama Connect REST API."""

    def __init__(
        self,
        settings: JamaSettings,
        credentials: JamaCredentials | None = None,
        *,
        client: httpx2.AsyncClient | None = None,
    ) -> None:
        """Create a client.

        Args:
            settings: Connection settings.
            credentials: The individual Jama account to act as. ``None`` leaves
                the client without an identity: every call then fails asking
                the caller to link their Jama account.
            client: An HTTP client to use instead of one of our own. Tests pass
                an ``AsyncClient`` backed by ``httpx2.MockTransport``; when
                omitted the connector creates and owns a client lazily.
        """
        self._settings = settings
        self._credentials = credentials if credentials and credentials.is_complete else None
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
    def credentials(self) -> JamaCredentials | None:
        return self._credentials

    @property
    def is_configured(self) -> bool:
        """True with both a Jama instance to reach and an account to act as."""
        return self._settings.is_configured and self._credentials is not None

    def with_credentials(self, credentials: JamaCredentials) -> "JamaClient":
        """A new client on the same instance, acting as ``credentials``.

        The new client owns its own HTTP client; the caller must ``aclose()`` it.
        """
        return JamaClient(self._settings, credentials)

    async def aclose(self) -> None:
        """Close the underlying HTTP client, if this connector owns it."""
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    # -- plumbing -----------------------------------------------------------

    def _ensure_configured(self) -> JamaCredentials:
        if not self._settings.is_configured:
            raise ConnectorNotConfiguredError(
                "Jama is not configured on this server. Set JAMA_BASE_URL in mcp-radia/.env.",
                system=SYSTEM,
            )
        if self._credentials is None:
            raise ConnectorNotConfiguredError(
                "No Jama account is linked for this request. Link your Jama account in "
                "RadiaAI Settings and try again. (Running mcp-radia locally over stdio? Set "
                "JAMA_CLIENT_ID and JAMA_CLIENT_SECRET to your own Jama OAuth client.)",
                system=SYSTEM,
            )
        return self._credentials

    def _get_client(self) -> httpx2.AsyncClient:
        if self._client is None:
            self._client = httpx2.AsyncClient(
                verify=self._settings.verify_ssl,
                timeout=self._settings.timeout_seconds,
            )
        return self._client

    async def _fetch_token(
        self, client: httpx2.AsyncClient, credentials: JamaCredentials
    ) -> str:
        """Exchange client credentials for a bearer token."""
        try:
            response = await client.post(
                self._settings.token_url,
                data={"grant_type": "client_credentials"},
                auth=httpx2.BasicAuth(credentials.client_id, credentials.client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
        except httpx2.HTTPStatusError as exc:
            raise ConnectorAuthError(
                "Jama rejected the OAuth token request for the linked Jama account. Its client "
                "id or secret may be wrong or revoked - re-link your Jama account in RadiaAI "
                "Settings.",
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

    async def _bearer_token(self, client: httpx2.AsyncClient, credentials: JamaCredentials) -> str:
        async with self._token_lock:
            if self._token is None or time.monotonic() >= self._token_expires_at:
                return await self._fetch_token(client, credentials)
            return self._token

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform an authenticated GET against the REST base and return parsed JSON."""
        credentials = self._ensure_configured()
        client = self._get_client()
        url = f"{self._settings.rest_base}/{path.lstrip('/')}"

        headers = {
            "Accept": "application/json",
            "Authorization": "Bearer " + await self._bearer_token(client, credentials),
        }

        try:
            response = await get_with_retry(
                client, url, system=SYSTEM, operation=path, params=params, headers=headers
            )
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
        remote = extract_remote_message(exc.response.text)
        if status == 404:
            raise ItemNotFoundError(
                "The requested Jama resource was not found. If this numeric id was derived from "
                "a document key (e.g. the '42' in SRS-42), that is not the same value as the "
                "numeric item id - call jama_search with the document key as the query to find "
                "the correct numeric id, then retry with that id. Do not assume the item was "
                "deleted or otherwise changed; this error only means the numeric id used was not "
                "found.",
                system=SYSTEM,
                operation=path,
                status_code=status,
                remote_message=remote,
            ) from exc
        if status in (401, 403):
            raise ConnectorAuthError(
                "Jama rejected the request. The linked Jama account may not have permission to "
                "read this item, or its credentials may have been revoked.",
                system=SYSTEM,
                operation=path,
                status_code=status,
                remote_message=remote,
            ) from exc
        raise ConnectorServiceError(
            "The Jama API returned an error response.",
            system=SYSTEM,
            operation=path,
            status_code=status,
            remote_message=remote,
        ) from exc

    # -- mapping ------------------------------------------------------------

    def _web_url(self, item_id: int, project_id: int | None) -> str | None:
        base = self._settings.base_url.rstrip("/")
        if not base:
            return None
        if project_id is None:
            return f"{base}/perspective.req#/items/{item_id}"
        return f"{base}/perspective.req#/items/{item_id}?projectId={project_id}"

    @staticmethod
    def _parent_id_from_raw(raw: dict[str, Any]) -> int | None:
        """Extract the document-tree parent id from Jama's ``location.parent.item``.

        A top-level item (no parent) omits ``location`` or ``location.parent``
        entirely rather than sending a null - both are treated as "no parent".
        """
        location = raw.get("location")
        if not isinstance(location, dict):
            return None
        parent = location.get("parent")
        if not isinstance(parent, dict):
            return None
        parent_item = parent.get("item")
        return int(parent_item) if isinstance(parent_item, int) else None

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
            parent_id=self._parent_id_from_raw(raw),
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
            parent_id=self._parent_id_from_raw(raw),
            created_date=raw.get("createdDate"),
            modified_date=raw.get("modifiedDate"),
            web_url=self._web_url(item_id, project_id),
            fields={k: v for k, v in fields.items() if k not in _FIELDS_SURFACED_ELSEWHERE},
        )

    @staticmethod
    def _project_from_raw(raw: dict[str, Any]) -> JamaProjectSummary:
        fields: dict[str, Any] = raw.get("fields") or {}
        return JamaProjectSummary(
            id=int(raw["id"]),
            project_key=raw.get("projectKey") or fields.get("projectKey"),
            name=str(fields.get("name") or ""),
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

    async def get_related_items(self, item_id: int) -> list[JamaRelatedItem]:
        """Return items linked to this one by Jama relationships, both directions.

        Uses ``/items/{id}/upstreamrelated`` and ``/downstreamrelated``, which
        return the related items themselves. The sibling ``*relationships``
        endpoints carry the relationship *type* but only item ids, which would
        cost an extra lookup per link; direction is the traceability signal
        that matters most here.
        """
        related: list[JamaRelatedItem] = []
        for direction, path in (
            ("upstream", "upstreamrelated"),
            ("downstream", "downstreamrelated"),
        ):
            payload = await self._get(
                f"items/{item_id}/{path}", params={"maxResults": MAX_PAGE_SIZE, "startAt": 0}
            )
            rows = payload.get("data") or []
            if not isinstance(rows, list):
                continue
            related.extend(
                JamaRelatedItem(direction=direction, item=self._summary_from_raw(row))
                for row in rows
                if isinstance(row, dict)
            )
        logger.info("jama_related_items_fetched", item_id=item_id, count=len(related))
        return related

    async def get_children(
        self,
        item_id: int,
        *,
        start_at: int = 0,
        max_results: int = MAX_PAGE_SIZE,
    ) -> JamaChildrenResult:
        """Return one page of an item's **direct** children.

        Uses ``/items/{id}/children``, which is the containment hierarchy: the
        items nested inside this one in the document tree (a folder's contents,
        the requirements under a set). This is deliberately *not* the same as
        :meth:`get_related_items`, which walks traceability links.

        Only one level is returned, and only one page of it. Recursing the
        whole subtree is left to the caller so a single tool call cannot fan
        out into an unbounded number of API requests.
        """
        capped = max(1, min(max_results, MAX_PAGE_SIZE))
        params: dict[str, Any] = {"startAt": max(0, start_at), "maxResults": capped}

        path = f"items/{item_id}/children"
        payload = await self._get(path, params=params)
        rows = payload.get("data") or []
        if not isinstance(rows, list):
            raise ConnectorServiceError(
                "Jama children returned an unexpected 'data' shape (expected a list).",
                system=SYSTEM,
                operation=path,
            )

        page_info = (payload.get("meta") or {}).get("pageInfo") or {}
        results = [self._summary_from_raw(row) for row in rows if isinstance(row, dict)]
        logger.info("jama_children_fetched", item_id=item_id, count=len(results))
        return JamaChildrenResult(
            parent_id=item_id,
            results=results,
            total=int(page_info.get("totalResults", len(results))),
            start_at=int(page_info.get("startIndex", start_at)),
            max_results=capped,
        )

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

    async def list_projects(
        self, *, start_at: int = 0, max_results: int = MAX_PAGE_SIZE
    ) -> list[JamaProjectSummary]:
        """List projects visible to the configured account.

        Exists so a caller can resolve a project's name or key (e.g. "the
        sandbox project") to the numeric id :meth:`search` requires, instead
        of guessing one - the same reason :meth:`search` itself exists for
        items. One page only: an instance's project count is normally small
        enough that paging is rarely needed, and the caller can pass
        ``start_at`` for the rare case it is.
        """
        capped = max(1, min(max_results, MAX_PAGE_SIZE))
        params: dict[str, Any] = {"startAt": max(0, start_at), "maxResults": capped}

        payload = await self._get("projects", params=params)
        raw_projects = payload.get("data") or []
        if not isinstance(raw_projects, list):
            raise ConnectorServiceError(
                "Jama projects returned an unexpected 'data' shape (expected a list).",
                system=SYSTEM,
                operation="projects",
            )

        results = [self._project_from_raw(p) for p in raw_projects if isinstance(p, dict)]
        logger.info("jama_projects_listed", count=len(results))
        return results
