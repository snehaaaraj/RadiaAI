"""Jama Connect REST API client.

Talks to a Jama instance over HTTPS using ``httpx``. Credentials are read from
:class:`app.core.config.JamaSettings` and never leave the backend. Two auth modes
are supported:

  - ``basic``  -> HTTP Basic auth (username/password or Jama API ID/key).
  - ``oauth``  -> OAuth 2.0 client-credentials; a bearer token is fetched from
                  ``/rest/oauth/token`` and cached until shortly before expiry.

The client exposes three read operations used by the requirement picker:

  - :meth:`list_projects`        -> GET /rest/v1/projects
  - :meth:`search_requirements`  -> GET /rest/v1/abstractitems
  - :meth:`get_requirement`      -> GET /rest/v1/items/{id}

All failures are surfaced as domain exceptions (``JamaNotConfiguredError``,
``JamaItemNotFoundError``, ``JamaServiceError``) so the API layer maps them to
consistent error envelopes.
"""

import html
import re
import time
from typing import Any, cast

import httpx

from app.core.config import JamaSettings
from app.core.exceptions import (
    JamaItemNotFoundError,
    JamaNotConfiguredError,
    JamaServiceError,
)
from app.core.logging import get_logger
from radia_ai.features.jama_requirement_reviewer.models.jama_models import (
    JamaProject,
    JamaRequirement,
    JamaRequirementSearchResult,
    JamaRequirementSummary,
)

logger = get_logger(__name__)

# Refresh OAuth tokens this many seconds before their stated expiry.
_TOKEN_EXPIRY_SKEW_SECONDS = 60

# Jama caps page size at 50 for most collection endpoints.
_MAX_PAGE_SIZE = 50

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")


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
    """Thin, read-only client over the Jama Connect REST API."""

    def __init__(self, settings: JamaSettings) -> None:
        self._settings = settings
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def is_configured(self) -> bool:
        return self._settings.is_configured

    # -- authentication -----------------------------------------------------

    def _ensure_configured(self) -> None:
        if not self._settings.is_configured:
            raise JamaNotConfiguredError(
                "Jama integration is not configured. Set JAMA_BASE_URL and credentials."
            )

    def _basic_auth(self) -> httpx.BasicAuth | None:
        if self._settings.auth_type == "basic":
            return httpx.BasicAuth(self._settings.username, self._settings.password)
        return None

    def _fetch_oauth_token(self, client: httpx.Client) -> str:
        """Exchange client credentials for a bearer token via the OAuth endpoint."""
        try:
            resp = client.post(
                self._settings.token_url,
                data={"grant_type": "client_credentials"},
                auth=httpx.BasicAuth(
                    self._settings.client_id, self._settings.client_secret
                ),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self._settings.timeout_seconds,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise JamaServiceError(
                "Jama OAuth token request was rejected.",
                operation="oauth_token",
                status_code=exc.response.status_code,
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
        self._token = cast(str, token)
        self._token_expires_at = time.monotonic() + expires_in - _TOKEN_EXPIRY_SKEW_SECONDS
        return self._token

    def _auth_headers(self, client: httpx.Client) -> dict[str, str]:
        """Return Authorization headers for OAuth mode (empty for basic auth)."""
        if self._settings.auth_type != "oauth":
            return {}
        if self._token is None or time.monotonic() >= self._token_expires_at:
            self._fetch_oauth_token(client)
        return {"Authorization": f"Bearer {self._token}"}

    # -- low-level request --------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform an authenticated GET against the REST base and return parsed JSON."""
        self._ensure_configured()
        url = f"{self._settings.rest_base}/{path.lstrip('/')}"
        auth = self._basic_auth()
        try:
            with httpx.Client(verify=self._settings.verify_ssl, auth=auth) as client:
                headers = self._auth_headers(client)
                resp = client.get(
                    url,
                    params=params,
                    headers={"Accept": "application/json", **headers},
                    timeout=self._settings.timeout_seconds,
                )
                resp.raise_for_status()
                return cast(dict[str, Any], resp.json())
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 404:
                raise JamaItemNotFoundError(
                    "The requested Jama resource was not found.",
                    detail={"path": path},
                ) from exc
            if status_code in (401, 403):
                raise JamaServiceError(
                    "Jama rejected the request. Check the configured credentials and permissions.",
                    operation=path,
                    status_code=status_code,
                    original_error=str(exc),
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
        """Return projects visible to the configured account (folders excluded)."""
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
