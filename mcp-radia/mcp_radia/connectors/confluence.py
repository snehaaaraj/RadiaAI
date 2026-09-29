"""Confluence Cloud REST API connector (read-only).

This connector deliberately spans **two API versions**, because neither one
covers both operations on Confluence Cloud today:

  - **Get page** uses v2, ``GET /wiki/api/v2/pages/{id}?body-format=storage``.
    v2 is the current API for content. Note the query parameter: the v1 idiom
    ``expand=body.storage`` is silently ignored by v2 and yields an empty
    ``body``, which is a common way to get blank pages back.
  - **Search** uses v1, ``GET /wiki/rest/api/search?cql=...``. CQL search has
    no v2 equivalent, so v1 remains the only way to run a real query.

Page bodies are returned in Confluence "storage format" (XHTML) and are
flattened to plain text.

Read operations only:

  - :meth:`ConfluenceClient.get_page` -> GET /wiki/api/v2/pages/{id}
  - :meth:`ConfluenceClient.search`   -> GET /wiki/rest/api/search
"""

from typing import Any

from pydantic import BaseModel, Field

from mcp_radia.connectors.atlassian import AtlassianClient
from mcp_radia.connectors.errors import ConnectorServiceError, ItemNotFoundError
from mcp_radia.connectors.text import strip_html
from mcp_radia.logging import get_logger

logger = get_logger(__name__)

SYSTEM = "confluence"
V2_BASE = "wiki/api/v2"
V1_BASE = "wiki/rest/api"

MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 25


def escape_cql_value(value: str) -> str:
    """Escape a user string for safe interpolation into a quoted CQL literal.

    CQL string literals are double-quoted, so a stray quote or backslash would
    otherwise let free text change the meaning of the query.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


class ConfluencePage(BaseModel):
    """A full Confluence page."""

    id: str = Field(description="Page id.")
    title: str = Field(default="", description="Page title.")
    space_id: str | None = Field(default=None, description="Id of the space holding the page.")
    status: str | None = Field(default=None, description="Page status, e.g. 'current'.")
    body: str = Field(default="", description="Page body, flattened from storage XHTML to text.")
    version: int | None = Field(default=None, description="Version number of this revision.")
    version_created_at: str | None = Field(
        default=None, description="ISO 8601 timestamp of this revision."
    )
    author_id: str | None = Field(default=None, description="Account id of the revision author.")
    web_url: str | None = Field(default=None, description="Browser URL for a human to open.")


class ConfluenceSearchHit(BaseModel):
    """A single row in a Confluence search result."""

    id: str | None = Field(default=None, description="Content id, usable with confluence_get_page.")
    title: str = Field(default="", description="Content title.")
    type: str | None = Field(default=None, description="Content type, e.g. page or blogpost.")
    space_key: str | None = Field(default=None, description="Key of the containing space.")
    excerpt: str = Field(default="", description="Search excerpt, with highlight markup removed.")
    last_modified: str | None = Field(default=None, description="ISO 8601 last-modified date.")
    web_url: str | None = Field(default=None, description="Browser URL for a human to open.")


class ConfluenceSearchResult(BaseModel):
    """A page of Confluence search results."""

    results: list[ConfluenceSearchHit] = Field(
        default_factory=list, description="Hits on this page."
    )
    total: int = Field(default=0, description="Total matches across all pages.")
    start: int = Field(default=0, description="Zero-based offset of the first hit returned.")
    limit: int = Field(default=0, description="Page size actually applied.")
    cql: str = Field(default="", description="The CQL that was executed.")


class ConfluenceClient(AtlassianClient):
    """Async, read-only client over the Confluence Cloud REST API."""

    system = SYSTEM
    config_hint = "ATLASSIAN_SITE_URL, ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN"

    def _web_url(self, webui_path: object) -> str | None:
        """Build an absolute URL from the relative ``_links.webui`` Confluence returns."""
        base = self._settings.base
        if not base or not isinstance(webui_path, str) or not webui_path:
            return None
        return f"{base}/wiki{webui_path}" if webui_path.startswith("/") else webui_path

    # -- public API ---------------------------------------------------------

    async def get_page(self, page_id: str) -> ConfluencePage:
        """Read a single page by id, including its body as plain text."""
        identifier = str(page_id).strip()
        payload = await self._get(
            f"{V2_BASE}/pages/{identifier}",
            # v2 spelling. 'expand=body.storage' is a v1 idiom and returns {} here.
            params={"body-format": "storage"},
        )
        if not payload.get("id"):
            raise ItemNotFoundError(
                f"Confluence page {identifier} was not found.",
                system=SYSTEM,
                operation=f"{V2_BASE}/pages/{identifier}",
                detail={"page_id": identifier},
            )

        body_container = payload.get("body") or {}
        storage = body_container.get("storage") if isinstance(body_container, dict) else None
        raw_body = storage.get("value") if isinstance(storage, dict) else None

        version = payload.get("version") or {}
        links = payload.get("_links") or {}

        page = ConfluencePage(
            id=str(payload["id"]),
            title=str(payload.get("title") or ""),
            space_id=str(payload["spaceId"]) if payload.get("spaceId") is not None else None,
            status=payload.get("status"),
            body=strip_html(raw_body),
            version=version.get("number") if isinstance(version, dict) else None,
            version_created_at=version.get("createdAt") if isinstance(version, dict) else None,
            author_id=version.get("authorId") if isinstance(version, dict) else None,
            web_url=self._web_url(links.get("webui") if isinstance(links, dict) else None),
        )
        logger.info("confluence_page_fetched", page_id=page.id, body_chars=len(page.body))
        return page

    def build_cql(
        self,
        *,
        query: str | None = None,
        space_key: str | None = None,
        content_type: str | None = None,
        cql: str | None = None,
    ) -> str:
        """Compose a CQL string from simple filters, or pass a raw one through.

        An explicit ``cql`` wins outright - it is the escape hatch for queries
        this helper cannot express.
        """
        if cql:
            return cql
        clauses: list[str] = []
        if query:
            clauses.append(f'text ~ "{escape_cql_value(query)}"')
        if space_key:
            clauses.append(f'space = "{escape_cql_value(space_key)}"')
        if content_type:
            clauses.append(f'type = "{escape_cql_value(content_type)}"')
        if not clauses:
            # CQL requires a predicate; this is the closest thing to "everything".
            clauses.append('type = "page"')
        return " AND ".join(clauses)

    async def search(
        self,
        *,
        query: str | None = None,
        space_key: str | None = None,
        content_type: str | None = None,
        cql: str | None = None,
        start: int = 0,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> ConfluenceSearchResult:
        """Search content via CQL."""
        capped = max(1, min(limit, MAX_PAGE_SIZE))
        effective_cql = self.build_cql(
            query=query, space_key=space_key, content_type=content_type, cql=cql
        )
        payload = await self._get(
            f"{V1_BASE}/search",
            params={"cql": effective_cql, "start": max(0, start), "limit": capped},
        )

        raw_results = payload.get("results") or []
        if not isinstance(raw_results, list):
            raise ConnectorServiceError(
                "Confluence search returned an unexpected 'results' shape (expected a list).",
                system=SYSTEM,
                operation=f"{V1_BASE}/search",
            )

        hits = [self._hit_from_raw(item) for item in raw_results if isinstance(item, dict)]
        logger.info("confluence_search_completed", cql=effective_cql, returned=len(hits))
        return ConfluenceSearchResult(
            results=hits,
            total=int(payload.get("totalSize", len(hits))),
            start=int(payload.get("start", start)),
            limit=capped,
            cql=effective_cql,
        )

    def _hit_from_raw(self, raw: dict[str, Any]) -> ConfluenceSearchHit:
        raw_content = raw.get("content")
        content: dict[str, Any] = raw_content if isinstance(raw_content, dict) else {}
        # Confluence wraps matched terms in @@@hl@@@ markers inside excerpts.
        excerpt = str(raw.get("excerpt") or "").replace("@@@hl@@@", "").replace("@@@endhl@@@", "")
        return ConfluenceSearchHit(
            id=str(content["id"]) if content.get("id") is not None else None,
            title=str(raw.get("title") or content.get("title") or ""),
            type=content.get("type") or raw.get("entityType"),
            space_key=self._space_key_from(raw, content),
            excerpt=strip_html(excerpt),
            last_modified=raw.get("lastModified"),
            web_url=self._web_url(raw.get("url")) if raw.get("url") else None,
        )

    @staticmethod
    def _space_key_from(raw: dict[str, Any], content: dict[str, Any]) -> str | None:
        """Find the space key, which v1 search reports in more than one place."""
        space = content.get("space")
        if isinstance(space, dict) and space.get("key"):
            return str(space["key"])
        container = raw.get("resultGlobalContainer")
        if isinstance(container, dict):
            display = container.get("displayUrl")
            # displayUrl looks like /spaces/ENG
            if isinstance(display, str) and "/spaces/" in display:
                return display.rsplit("/spaces/", 1)[-1].split("/")[0] or None
        return None
