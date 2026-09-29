"""Mock HTTP plumbing and sample payloads for the Jira and Confluence tests.

Payload shapes follow Atlassian Cloud's documented responses: Jira v3 with ADF
descriptions and token-paginated search, Confluence v2 pages with a
storage-format body plus v1 CQL search results.
"""

from collections.abc import Callable
from typing import Any

import httpx2

from mcp_radia.connectors.atlassian import AtlassianSettings
from mcp_radia.connectors.confluence import ConfluenceClient
from mcp_radia.connectors.jira import JiraClient
from tests.jama_fixtures import RecordingHandler

SITE = "https://example.atlassian.net"


def atlassian_settings(**overrides: Any) -> AtlassianSettings:
    """Fully configured Cloud settings, insulated from any real .env."""
    values: dict[str, Any] = {
        "site_url": SITE,
        "email": "svc-radia@example.com",
        "api_token": "tok-secret",
    }
    values.update(overrides)
    return AtlassianSettings(_env_file=None, **values)


# -- Jira payloads -----------------------------------------------------------

ADF_DESCRIPTION: dict[str, Any] = {
    "type": "doc",
    "version": 1,
    "content": [
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Cell balancing fails above "},
                {"type": "text", "text": "45C", "marks": [{"type": "strong"}]},
                {"type": "text", "text": "."},
            ],
        },
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Raised by "},
                {"type": "mention", "attrs": {"id": "abc", "text": "@Dana Ruiz"}},
                {"type": "text", "text": " see "},
                {"type": "inlineCard", "attrs": {"url": "https://example.atlassian.net/wiki/x/1"}},
            ],
        },
    ],
}

ISSUE_PAYLOAD: dict[str, Any] = {
    "id": "10001",
    "key": "BMS-451",
    "fields": {
        "summary": "Cell balancing fails at high temperature",
        "description": ADF_DESCRIPTION,
        "status": {"name": "In Progress"},
        "issuetype": {"name": "Bug"},
        "project": {"key": "BMS", "name": "Battery Management"},
        "assignee": {"displayName": "Dana Ruiz"},
        "reporter": {"displayName": "Sam Okafor"},
        "priority": {"name": "High"},
        "labels": ["safety", "thermal"],
        "parent": {"key": "BMS-400"},
        "created": "2026-01-05T10:00:00.000+0000",
        "updated": "2026-02-11T14:30:00.000+0000",
        "issuelinks": [
            {
                "type": {"name": "Blocks", "inward": "is blocked by", "outward": "blocks"},
                "outwardIssue": {
                    "key": "BMS-452",
                    "fields": {"summary": "Thermal model update", "status": {"name": "To Do"}},
                },
            },
            {
                "type": {"name": "Relates", "inward": "relates to", "outward": "relates to"},
                "inwardIssue": {
                    "key": "BMS-300",
                    "fields": {"summary": "Original thermal spec", "status": {"name": "Done"}},
                },
            },
        ],
    },
}

SEARCH_PAYLOAD: dict[str, Any] = {
    "issues": [
        {
            "id": "10001",
            "key": "BMS-451",
            "fields": {
                "summary": "Cell balancing fails at high temperature",
                "status": {"name": "In Progress"},
                "issuetype": {"name": "Bug"},
                "project": {"key": "BMS"},
                "assignee": {"displayName": "Dana Ruiz"},
                "priority": {"name": "High"},
                "created": "2026-01-05T10:00:00.000+0000",
                "updated": "2026-02-11T14:30:00.000+0000",
            },
        },
        {
            "id": "10002",
            "key": "BMS-452",
            "fields": {
                "summary": "Thermal model update",
                "status": {"name": "To Do"},
                "issuetype": {"name": "Task"},
                "project": {"key": "BMS"},
                "assignee": None,
            },
        },
    ],
    "nextPageToken": "tok-page-2",
    "isLast": False,
}

# -- Confluence payloads -----------------------------------------------------

PAGE_PAYLOAD: dict[str, Any] = {
    "id": "123456789",
    "title": "Battery Thermal Design",
    "spaceId": "555",
    "status": "current",
    "version": {"number": 7, "createdAt": "2026-02-10T09:00:00Z", "authorId": "acc-1"},
    "body": {
        "storage": {
            "value": (
                "<p>Thermal limits are defined in <strong>SRS-42</strong>.</p>"
                "<style>.x{color:red}</style>"
                "<ul><li>Upper bound 45C</li><li>Lower bound -20C</li></ul>"
            ),
            "representation": "storage",
        }
    },
    "_links": {"webui": "/spaces/ENG/pages/123456789/Battery+Thermal+Design"},
}

SEARCH_RESULTS_PAYLOAD: dict[str, Any] = {
    "results": [
        {
            "content": {"id": "123456789", "type": "page", "space": {"key": "ENG"}},
            "title": "Battery Thermal Design",
            "excerpt": "Thermal limits are defined in @@@hl@@@SRS-42@@@endhl@@@.",
            "url": "/spaces/ENG/pages/123456789/Battery+Thermal+Design",
            "lastModified": "2026-02-10T09:00:00Z",
            "entityType": "content",
        },
        {
            "content": {"id": "987654321", "type": "blogpost"},
            "title": "Thermal retro",
            "excerpt": "What we learned",
            "url": "/spaces/ENG/blog/987654321",
            "resultGlobalContainer": {"title": "Engineering", "displayUrl": "/spaces/ENG"},
        },
    ],
    "start": 0,
    "limit": 25,
    "totalSize": 42,
}


# -- client builders ---------------------------------------------------------


def make_jira_client(
    responder: Callable[[httpx2.Request], httpx2.Response],
    settings: AtlassianSettings | None = None,
) -> tuple[JiraClient, RecordingHandler]:
    handler = RecordingHandler(responder)
    http_client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return JiraClient(settings or atlassian_settings(), client=http_client), handler


def make_confluence_client(
    responder: Callable[[httpx2.Request], httpx2.Response],
    settings: AtlassianSettings | None = None,
) -> tuple[ConfluenceClient, RecordingHandler]:
    handler = RecordingHandler(responder)
    http_client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return ConfluenceClient(settings or atlassian_settings(), client=http_client), handler
