"""Jama Connect REST API client.

Talks to a Jama instance over HTTPS using ``httpx``. Credentials never leave the
backend. Two credential sources are supported:

  - **Per-user** (production): the signed-in user's own Jama API credentials
    (client ID / secret created under their Jama profile -> "Set API Credentials").
    Tokens are obtained with the OAuth 2.0 client-credentials grant and Jama
    enforces *that user's* project permissions on every call.
  - **Shared service account** (local development only), from ``JamaSettings``:
      - ``basic``  -> HTTP Basic auth (username/password or Jama API ID/key).
      - ``oauth``  -> OAuth 2.0 client-credentials.

Bearer tokens are fetched from ``/rest/oauth/token`` and cached until shortly
before expiry in a :class:`JamaTokenCache` that can be shared across requests.

Operations used by the app:

  - :meth:`list_projects`        -> GET /rest/v1/projects
  - :meth:`search_requirements`  -> GET /rest/v1/abstractitems
  - :meth:`get_requirement`      -> GET /rest/v1/items/{id}
  - :meth:`get_current_user`     -> GET /rest/v1/users/current

All failures are surfaced as domain exceptions so the API layer maps them to
consistent error envelopes.
"""

import hashlib
import html
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, cast

import httpx

from app.core.config import JamaSettings
from app.core.exceptions import (
    JamaCredentialsInvalidError,
    JamaItemNotFoundError,
    JamaNotConfiguredError,
    JamaPermissionDeniedError,
    JamaServiceError,
)
from app.core.logging import get_logger
from radia_ai.features.jama_requirement_reviewer.models.jama_models import (
    JamaProject,
    JamaRequirement,
    JamaRequirementSearchResult,
    JamaRequirementSummary,
    JamaUserProfile,
)

logger = get_logger(__name__)

# Refresh OAuth tokens this many seconds before their stated expiry.
_TOKEN_EXPIRY_SKEW_SECONDS = 60

# Jama caps page size at 50 for most collection endpoints.
_MAX_PAGE_SIZE = 50

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")


@dataclass(frozen=True)
class JamaApiCredentials:
    """A Jama OAuth client ID / secret pair. The secret is excluded from repr."""

    client_id: str
    client_secret: str = field(repr=False)


class JamaTokenCache:
    """Thread-safe cache of Jama bearer tokens keyed by a hash of the credentials."""

    def __init__(self, max_entries: int = 1024) -> None:
        self._entries: dict[str, tuple[str, float]] = {}
        self._max_entries = max_entries
        self._lock = threading.Lock()

    @staticmethod
    def key_for(token_url: str, credentials: JamaApiCredentials) -> str:
        material = f"{token_url}\0{credentials.client_id}\0{credentials.client_secret}"
        return hashlib.sha256(material.encode()).hexdigest()

    def get(self, key: str) -> str | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            token, expires_at = entry
            if time.monotonic() >= expires_at:
                self._entries.pop(key, None)
                return None
            return token

    def put(self, key: str, token: str, expires_at: float) -> None:
        with self._lock:
            if len(self._entries) >= self._max_entries:
                now = time.monotonic()
                self._entries = {k: v for k, v in self._entries.items() if v[1] > now}
                if len(self._entries) >= self._max_entries:
                    self._entries.pop(next(iter(self._entries)))
            self._entries[key] = (token, expires_at)

    def discard(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)


def _strip_html(value: str | None) -> str:
    """Convert a Jama rich-text (HTML) field into readable plain text."""
    if not value:
        return ""
    # Turn block-level breaks into newlines before stripping tags.
    text = re.sub(r"(?i)<br\s*/?>", "\n", value)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    # Collapse runs of spaces but preserve newlines.
    lines = [_WS_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line != "").strip()


class JamaClient:
    """Thin client over the Jama Connect REST API, scoped to one credential set."""

    def __init__(
        self,
        settings: JamaSettings,
        credentials: JamaApiCredentials | None = None,
        token_cache: JamaTokenCache | None = None,
    ) -> None:
        self._settings = settings
        self._credentials = credentials
        self._token_cache = token_cache or JamaTokenCache(max_entries=4)

    @property
    def is_user_scoped(self) -> bool:
        """True when calls run as an individual user's linked Jama account."""
        return self._credentials is not None

    @property
    def is_configured(self) -> bool:
        if self._credentials is not None:
            return self._settings.has_base_url
        return self._settings.is_configured

    def probe(self) -> None:
        """Verify authenticated access without retrieving the full project catalog."""
        self.list_projects(max_results=1)

    # -- authentication -----------------------------------------------------

    def _ensure_configured(self) -> None:
        if not self.is_configured:
            raise JamaNotConfiguredError(
                "Jama integration is not configured. Set JAMA_BASE_URL and credentials."
            )

    def _uses_oauth(self) -> bool:
        return self._credentials is not None or self._settings.auth_type == "oauth"

    def _oauth_credentials(self) -> JamaApiCredentials:
        if self._credentials is not None:
            return self._credentials
        return JamaApiCredentials(self._settings.client_id, self._settings.client_secret)

    def _basic_auth(self) -> httpx.BasicAuth | None:
        if self._uses_oauth():
            return None
        return httpx.BasicAuth(self._settings.username, self._settings.password)

    def _fetch_oauth_token(self, client: httpx.Client, cache_key: str) -> str:
        """Exchange client credentials for a bearer token via the OAuth endpoint."""
        credentials = self._oauth_credentials()
        try:
            resp = client.post(
                self._settings.token_url,
                data={"grant_type": "client_credentials"},
                auth=httpx.BasicAuth(credentials.client_id, credentials.client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self._settings.timeout_seconds,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if self.is_user_scoped and status_code in (400, 401, 403):
                raise JamaCredentialsInvalidError(
                    "Jama rejected your linked API credentials. They may have been revoked or "
                    "deleted - re-link your Jama account in Settings.",
                    detail={"jama_status_code": status_code},
                ) from exc
            raise JamaServiceError(
                "Jama OAuth token request was rejected.",
                operation="oauth_token",
                status_code=status_code,
                original_error=str(exc),
            ) from exc
        except httpx.HTTPError as exc:
            raise JamaServiceError(
                "Could not reach the Jama OAuth token endpoint.",
                operation="oauth_token",
                original_error=str(exc),
            ) from exc

        payload = resp.json()
        token = payload.get("access_token")
        if not token:
            raise JamaServiceError(
                "Jama OAuth response did not contain an access token.",
                operation="oauth_token",
            )
        expires_in = float(payload.get("expires_in", 3600))
        expires_at = time.monotonic() + max(0.0, expires_in - _TOKEN_EXPIRY_SKEW_SECONDS)
        self._token_cache.put(cache_key, cast(str, token), expires_at)
        return cast(str, token)

    def _token_cache_key(self) -> str:
        return JamaTokenCache.key_for(self._settings.token_url, self._oauth_credentials())

    def _auth_headers(self, client: httpx.Client) -> dict[str, str]:
        """Return Authorization headers for OAuth mode (empty for basic auth)."""
        if not self._uses_oauth():
            return {}
        cache_key = self._token_cache_key()
        token = self._token_cache.get(cache_key) or self._fetch_oauth_token(client, cache_key)
        return {"Authorization": "Bearer " + token}

    # -- low-level request --------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform an authenticated GET against the REST base and return parsed JSON."""
        return self._request("GET", path, params=params)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[Any] | None = None,
    ) -> dict[str, Any]:
        """
        Perform an authenticated request against the REST base and return parsed JSON.

        Write operations (Jama round-trip) must go through this method with a
        user-scoped client so Jama enforces the signed-in user's project permissions.
        """
        self._ensure_configured()
        url = f"{self._settings.rest_base}/{path.lstrip('/')}"
        auth = self._basic_auth()
        try:
            with httpx.Client(verify=self._settings.verify_ssl, auth=auth) as client:
                headers = self._auth_headers(client)
                resp = client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers={"Accept": "application/json", **headers},
                    timeout=self._settings.timeout_seconds,
                )
                resp.raise_for_status()
                return cast(dict[str, Any], resp.json()) if resp.content else {}
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 404:
                raise JamaItemNotFoundError(
                    "The requested Jama resource was not found.",
                    detail={"path": path},
                ) from exc
            if status_code == 401:
                if self._uses_oauth():
                    self._token_cache.discard(self._token_cache_key())
                if self.is_user_scoped:
                    raise JamaCredentialsInvalidError(
                        "Jama rejected your linked API credentials. Re-link your Jama account "
                        "in Settings.",
                        detail={"jama_status_code": status_code},
                    ) from exc
                raise JamaServiceError(
                    "Jama rejected the request. Check the configured credentials and permissions.",
                    operation=path,
                    status_code=status_code,
                    original_error=str(exc),
                ) from exc
            if status_code == 403:
                raise JamaPermissionDeniedError(
                    "Your Jama account does not have permission to access this Jama resource.",
                    detail={"path": path, "jama_status_code": status_code},
                ) from exc
            raise JamaServiceError(
                "Jama API returned an error response.",
                operation=path,
                status_code=status_code,
                original_error=str(exc),
            ) from exc
        except httpx.HTTPError as exc:
            raise JamaServiceError(
                "Could not reach the Jama API.",
                operation=path,
                original_error=str(exc),
            ) from exc

    # -- mapping helpers ----------------------------------------------------

    @staticmethod
    def _project_from_raw(raw: dict[str, Any]) -> JamaProject:
        fields = raw.get("fields", {}) or {}
        name = fields.get("name") or raw.get("projectKey") or f"Project {raw.get('id')}"
        return JamaProject(
            id=int(raw["id"]),
            name=str(name),
            project_key=raw.get("projectKey"),
            is_folder=bool(raw.get("isFolder", False)),
        )

    @staticmethod
    def _summary_from_raw(raw: dict[str, Any]) -> JamaRequirementSummary:
        fields = raw.get("fields", {}) or {}
        return JamaRequirementSummary(
            id=int(raw["id"]),
            document_key=raw.get("documentKey"),
            global_id=raw.get("globalId"),
            name=str(fields.get("name", "") or ""),
            item_type_id=raw.get("itemType"),
            project_id=raw.get("project"),
        )

    def _requirement_from_raw(self, raw: dict[str, Any]) -> JamaRequirement:
        fields = cast(dict[str, Any], raw.get("fields", {}) or {})
        status = fields.get("status")
        project_id = raw.get("project")
        item_id = int(raw["id"])
        return JamaRequirement(
            id=item_id,
            document_key=raw.get("documentKey"),
            global_id=raw.get("globalId"),
            name=str(fields.get("name", "") or ""),
            description=_strip_html(fields.get("description")),
            rationale=_strip_html(fields.get("rationale")),
            status=str(status) if status is not None else None,
            item_type_id=raw.get("itemType"),
            project_id=project_id,
            created_date=raw.get("createdDate"),
            modified_date=raw.get("modifiedDate"),
            web_url=self._item_web_url(item_id, project_id),
            fields=fields,
        )

    def _item_web_url(self, item_id: int, project_id: int | None) -> str | None:
        base = self._settings.base_url.rstrip("/")
        if not base:
            return None
        if project_id is None:
            return f"{base}/perspective.req#/items/{item_id}"
        return f"{base}/perspective.req#/items/{item_id}?projectId={project_id}"

    # -- public API ---------------------------------------------------------

    def list_projects(self, *, max_results: int = _MAX_PAGE_SIZE) -> list[JamaProject]:
        """Return projects visible to the authenticated Jama account (folders excluded)."""
        capped = max(1, min(max_results, _MAX_PAGE_SIZE))
        payload = self._get("projects", params={"maxResults": capped, "startAt": 0})
        data = cast(list[dict[str, Any]], payload.get("data", []))
        projects = [self._project_from_raw(item) for item in data]
        return [p for p in projects if not p.is_folder]

    def search_requirements(
        self,
        *,
        project_id: int | None = None,
        contains: str | None = None,
        item_type_id: int | None = None,
        start_at: int = 0,
        max_results: int = _MAX_PAGE_SIZE,
    ) -> JamaRequirementSearchResult:
        """Search/list items, optionally scoped to a project and free-text query."""
        capped = max(1, min(max_results, _MAX_PAGE_SIZE))
        params: dict[str, Any] = {"startAt": max(0, start_at), "maxResults": capped}
        if project_id is not None:
            params["project"] = project_id
        if contains:
            params["contains"] = contains
        if item_type_id is not None:
            params["itemType"] = item_type_id

        payload = self._get("abstractitems", params=params)
        data = cast(list[dict[str, Any]], payload.get("data", []))
        page_info = cast(dict[str, Any], payload.get("meta", {}).get("pageInfo", {}) or {})
        results = [self._summary_from_raw(item) for item in data]
        return JamaRequirementSearchResult(
            results=results,
            total=int(page_info.get("totalResults", len(results))),
            start_at=int(page_info.get("startIndex", start_at)),
            max_results=capped,
        )

    def get_requirement(self, item_id: int) -> JamaRequirement:
        """Read a single item by numeric id and normalize it to a requirement."""
        payload = self._get(f"items/{item_id}")
        data = payload.get("data")
        if not data:
            raise JamaItemNotFoundError(
                f"Jama item {item_id} was not found.",
                detail={"item_id": item_id},
            )
        return self._requirement_from_raw(cast(dict[str, Any], data))

    def get_current_user(self) -> JamaUserProfile:
        """Return the Jama user the current credentials authenticate as."""
        payload = self._get("users/current")
        data = cast(dict[str, Any], payload.get("data") or {})
        if "id" not in data:
            raise JamaServiceError(
                "Jama did not return the current user.", operation="users/current"
            )
        first = str(data.get("firstName") or "").strip()
        last = str(data.get("lastName") or "").strip()
        return JamaUserProfile(
            id=int(data["id"]),
            username=str(data.get("username") or ""),
            email=str(data.get("email") or ""),
            display_name=" ".join(part for part in (first, last) if part),
            active=bool(data.get("active", True)),
        )
