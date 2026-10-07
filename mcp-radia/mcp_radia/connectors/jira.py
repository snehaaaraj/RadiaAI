"""Jira Cloud REST API connector (read-only).

Talks to the Jira Cloud platform REST API v3 at ``{site}/rest/api/3``.

Two things about v3 drive the shape of this module:

1. **Search uses the token-paginated endpoint.** ``GET /rest/api/3/search`` was
   deprecated in 2024 and replaced by ``GET /rest/api/3/search/jql``, which
   drops ``startAt`` in favour of an opaque ``nextPageToken`` and returns
   **no total count**. :class:`JiraSearchResult` therefore exposes
   ``next_page_token``/``is_last`` instead of a total, and callers page by
   feeding the token back in.

2. **Fields must be requested explicitly.** ``/search/jql`` returns only ``id``
   and ``key`` unless ``fields`` is passed, which is a common way to get
   mysteriously empty results. :data:`SEARCH_FIELDS` is always sent.

Descriptions come back as Atlassian Document Format (ADF) JSON rather than
text, and are flattened by :func:`mcp_radia.connectors.text.adf_to_text`.

Read operations only:

  - :meth:`JiraClient.get_issue` -> GET /rest/api/3/issue/{key}
  - :meth:`JiraClient.search`    -> GET /rest/api/3/search/jql
"""

from typing import Any

from pydantic import BaseModel, Field

from mcp_radia.connectors.atlassian import AtlassianClient
from mcp_radia.connectors.errors import ConnectorServiceError, ItemNotFoundError
from mcp_radia.connectors.text import adf_to_text
from mcp_radia.logging import get_logger

logger = get_logger(__name__)

SYSTEM = "jira"
API_BASE = "rest/api/3"

# Jira Cloud accepts far more, but large pages produce responses too big to be
# useful to a model. 100 is a deliberate ceiling, not the API's.
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25

#: Fields requested on search. Without an explicit list, /search/jql returns
#: only id and key.
SEARCH_FIELDS = (
    "summary",
    "status",
    "issuetype",
    "project",
    "assignee",
    "priority",
    "created",
    "updated",
)

#: Fields requested on a single issue: the search set plus the expensive ones.
ISSUE_FIELDS = (*SEARCH_FIELDS, "description", "labels", "issuelinks", "reporter", "parent")


def _nested_name(value: object) -> str | None:
    """Pull ``name`` out of a nested Jira object such as status or issuetype."""
    if isinstance(value, dict):
        name = value.get("name")
        return str(name) if name is not None else None
    return None


def _display_name(value: object) -> str | None:
    """Pull ``displayName`` out of a Jira user object."""
    if isinstance(value, dict):
        name = value.get("displayName")
        return str(name) if name is not None else None
    return None


class JiraIssueSummary(BaseModel):
    """A single row in a Jira search result."""

    key: str = Field(description="Issue key, e.g. PROJ-123.")
    id: str | None = Field(default=None, description="Numeric issue id, as a string.")
    summary: str = Field(default="", description="Issue summary / title.")
    status: str | None = Field(default=None, description="Workflow status name.")
    issue_type: str | None = Field(default=None, description="Issue type name, e.g. Bug.")
    project_key: str | None = Field(default=None, description="Key of the owning project.")
    assignee: str | None = Field(default=None, description="Display name of the assignee.")
    priority: str | None = Field(default=None, description="Priority name.")
    created: str | None = Field(default=None, description="ISO 8601 creation timestamp.")
    updated: str | None = Field(default=None, description="ISO 8601 last-updated timestamp.")
    web_url: str | None = Field(default=None, description="Browser URL for a human to open.")


class JiraIssueLink(BaseModel):
    """One end of a Jira issue link, flattened into a single direction."""

    type: str = Field(description="Link type as read from this issue, e.g. 'blocks'.")
    direction: str = Field(description="Either 'inward' or 'outward'.")
    key: str = Field(description="Key of the issue on the other end.")
    summary: str = Field(default="", description="Summary of the linked issue.")
    status: str | None = Field(default=None, description="Status of the linked issue.")


class JiraIssue(BaseModel):
    """A full Jira issue."""

    key: str = Field(description="Issue key, e.g. PROJ-123.")
    id: str | None = Field(default=None, description="Numeric issue id, as a string.")
    summary: str = Field(default="", description="Issue summary / title.")
    description: str = Field(default="", description="Description, flattened from ADF to text.")
    status: str | None = Field(default=None, description="Workflow status name.")
    issue_type: str | None = Field(default=None, description="Issue type name.")
    project_key: str | None = Field(default=None, description="Key of the owning project.")
    assignee: str | None = Field(default=None, description="Display name of the assignee.")
    reporter: str | None = Field(default=None, description="Display name of the reporter.")
    priority: str | None = Field(default=None, description="Priority name.")
    labels: list[str] = Field(default_factory=list, description="Labels on the issue.")
    parent_key: str | None = Field(default=None, description="Key of the parent issue, if any.")
    created: str | None = Field(default=None, description="ISO 8601 creation timestamp.")
    updated: str | None = Field(default=None, description="ISO 8601 last-updated timestamp.")
    links: list[JiraIssueLink] = Field(
        default_factory=list,
        description="Issue links, used as native cross-references in the digital thread.",
    )
    web_url: str | None = Field(default=None, description="Browser URL for a human to open.")


class JiraSearchResult(BaseModel):
    """A page of Jira search results.

    Jira Cloud's current search endpoint is token-paginated and returns no
    total, so there is deliberately no ``total`` field here.
    """

    results: list[JiraIssueSummary] = Field(
        default_factory=list, description="Issues on this page."
    )
    next_page_token: str | None = Field(
        default=None,
        description="Pass back as next_page_token to fetch the following page. Null when done.",
    )
    is_last: bool = Field(default=True, description="True when this is the final page.")
    jql: str = Field(default="", description="The JQL that was executed.")


class JiraClient(AtlassianClient):
    """Async, read-only client over the Jira Cloud REST API v3."""

    system = SYSTEM
    config_hint = "ATLASSIAN_SITE_URL, ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN"

    def _web_url(self, key: str) -> str | None:
        base = self._settings.base
        return f"{base}/browse/{key}" if base else None

    def _summary_from_raw(self, raw: dict[str, Any]) -> JiraIssueSummary:
        fields: dict[str, Any] = raw.get("fields") or {}
        key = str(raw.get("key", ""))
        project = fields.get("project")
        return JiraIssueSummary(
            key=key,
            id=str(raw["id"]) if raw.get("id") is not None else None,
            summary=str(fields.get("summary") or ""),
            status=_nested_name(fields.get("status")),
            issue_type=_nested_name(fields.get("issuetype")),
            project_key=str(project.get("key")) if isinstance(project, dict) else None,
            assignee=_display_name(fields.get("assignee")),
            priority=_nested_name(fields.get("priority")),
            created=fields.get("created"),
            updated=fields.get("updated"),
            web_url=self._web_url(key),
        )

    @staticmethod
    def _links_from_raw(raw_links: object) -> list[JiraIssueLink]:
        """Flatten Jira's inward/outward link structure into one list.

        Jira reports a link as either an ``inwardIssue`` or an ``outwardIssue``
        plus a type object carrying both phrasings. Recording the direction and
        the phrasing that applies *from this issue* keeps the relationship
        readable without the caller re-deriving it.
        """
        links: list[JiraIssueLink] = []
        if not isinstance(raw_links, list):
            return links
        for entry in raw_links:
            if not isinstance(entry, dict):
                continue
            link_type = entry.get("type") or {}
            for direction, key_name in (("inward", "inwardIssue"), ("outward", "outwardIssue")):
                other = entry.get(key_name)
                if not isinstance(other, dict):
                    continue
                other_fields = other.get("fields") or {}
                links.append(
                    JiraIssueLink(
                        type=str(link_type.get(direction) or link_type.get("name") or "relates"),
                        direction=direction,
                        key=str(other.get("key", "")),
                        summary=str(other_fields.get("summary") or ""),
                        status=_nested_name(other_fields.get("status")),
                    )
                )
        return links

    def _issue_from_raw(self, raw: dict[str, Any]) -> JiraIssue:
        fields: dict[str, Any] = raw.get("fields") or {}
        key = str(raw.get("key", ""))
        project = fields.get("project")
        parent = fields.get("parent")
        labels = fields.get("labels")
        return JiraIssue(
            key=key,
            id=str(raw["id"]) if raw.get("id") is not None else None,
            summary=str(fields.get("summary") or ""),
            description=adf_to_text(fields.get("description")),
            status=_nested_name(fields.get("status")),
            issue_type=_nested_name(fields.get("issuetype")),
            project_key=str(project.get("key")) if isinstance(project, dict) else None,
            assignee=_display_name(fields.get("assignee")),
            reporter=_display_name(fields.get("reporter")),
            priority=_nested_name(fields.get("priority")),
            labels=[str(label) for label in labels] if isinstance(labels, list) else [],
            parent_key=str(parent.get("key")) if isinstance(parent, dict) else None,
            created=fields.get("created"),
            updated=fields.get("updated"),
            links=self._links_from_raw(fields.get("issuelinks")),
            web_url=self._web_url(key),
        )

    # -- public API ---------------------------------------------------------

    async def get_issue(self, issue_key: str) -> JiraIssue:
        """Read a single issue by key (``PROJ-123``) or numeric id."""
        key = issue_key.strip()
        payload = await self._get(
            f"{API_BASE}/issue/{key}",
            params={"fields": ",".join(ISSUE_FIELDS)},
        )
        if not payload.get("key") and not payload.get("id"):
            raise ItemNotFoundError(
                f"Jira issue {key} was not found.",
                system=SYSTEM,
                operation=f"{API_BASE}/issue/{key}",
                detail={"issue_key": key},
            )
        issue = self._issue_from_raw(payload)
        logger.info("jira_issue_fetched", issue_key=issue.key, link_count=len(issue.links))
        return issue

    async def search(
        self,
        *,
        jql: str,
        next_page_token: str | None = None,
        max_results: int = DEFAULT_PAGE_SIZE,
    ) -> JiraSearchResult:
        """Run a JQL search against the token-paginated search endpoint."""
        capped = max(1, min(max_results, MAX_PAGE_SIZE))
        params: dict[str, Any] = {
            "jql": jql,
            "maxResults": capped,
            # Without this the endpoint returns only id and key.
            "fields": ",".join(SEARCH_FIELDS),
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token

        payload = await self._get(f"{API_BASE}/search/jql", params=params)
        raw_issues = payload.get("issues") or []
        if not isinstance(raw_issues, list):
            raise ConnectorServiceError(
                "Jira search returned an unexpected 'issues' shape (expected a list).",
                system=SYSTEM,
                operation=f"{API_BASE}/search/jql",
            )

        token = payload.get("nextPageToken")
        results = [self._summary_from_raw(item) for item in raw_issues if isinstance(item, dict)]
        logger.info("jira_search_completed", jql=jql, returned=len(results))
        return JiraSearchResult(
            results=results,
            next_page_token=str(token) if token else None,
            # Trust isLast when present; otherwise the absence of a token means done.
            is_last=bool(payload.get("isLast", token is None)),
            jql=jql,
        )
