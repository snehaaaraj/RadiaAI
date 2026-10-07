"""Unit tests for the Jira Cloud connector. All HTTP is mocked."""

import base64

import httpx2
import pytest

from mcp_radia.connectors.errors import (
    ConnectorAuthError,
    ConnectorNotConfiguredError,
    ConnectorServiceError,
    ItemNotFoundError,
)
from mcp_radia.connectors.jira import MAX_PAGE_SIZE
from tests.atlassian_fixtures import (
    ISSUE_PAYLOAD,
    SEARCH_PAYLOAD,
    atlassian_settings,
    make_jira_client,
)
from tests.jama_fixtures import json_responder

pytestmark = pytest.mark.unit


# -- get_issue ---------------------------------------------------------------


async def test_get_issue_maps_payload_to_model() -> None:
    client, handler = make_jira_client(json_responder(ISSUE_PAYLOAD))

    issue = await client.get_issue("BMS-451")

    assert issue.key == "BMS-451"
    assert issue.id == "10001"
    assert issue.summary == "Cell balancing fails at high temperature"
    assert issue.status == "In Progress"
    assert issue.issue_type == "Bug"
    assert issue.project_key == "BMS"
    assert issue.assignee == "Dana Ruiz"
    assert issue.reporter == "Sam Okafor"
    assert issue.priority == "High"
    assert issue.labels == ["safety", "thermal"]
    assert issue.parent_key == "BMS-400"
    assert handler.last_request.url.path == "/rest/api/3/issue/BMS-451"


async def test_get_issue_flattens_the_adf_description() -> None:
    """Jira v3 returns ADF JSON, which is useless to a model unless flattened."""
    client, _ = make_jira_client(json_responder(ISSUE_PAYLOAD))

    issue = await client.get_issue("BMS-451")

    assert "Cell balancing fails above 45C." in issue.description
    assert "@Dana Ruiz" in issue.description
    assert "https://example.atlassian.net/wiki/x/1" in issue.description
    assert "{" not in issue.description, "raw ADF JSON leaked into the description"


async def test_get_issue_requests_fields_explicitly() -> None:
    """Without an explicit fields list Jira returns a stripped-down issue."""
    client, handler = make_jira_client(json_responder(ISSUE_PAYLOAD))

    await client.get_issue("BMS-451")

    fields = handler.last_request.url.params["fields"]
    assert "description" in fields
    assert "issuelinks" in fields


async def test_get_issue_flattens_links_in_both_directions() -> None:
    client, _ = make_jira_client(json_responder(ISSUE_PAYLOAD))

    issue = await client.get_issue("BMS-451")

    by_key = {link.key: link for link in issue.links}
    assert set(by_key) == {"BMS-452", "BMS-300"}
    # Phrasing is recorded from this issue's point of view.
    assert by_key["BMS-452"].direction == "outward"
    assert by_key["BMS-452"].type == "blocks"
    assert by_key["BMS-452"].summary == "Thermal model update"
    assert by_key["BMS-300"].direction == "inward"
    assert by_key["BMS-300"].type == "relates to"
    assert by_key["BMS-300"].status == "Done"


async def test_get_issue_builds_a_browse_url() -> None:
    client, _ = make_jira_client(json_responder(ISSUE_PAYLOAD))

    issue = await client.get_issue("BMS-451")

    assert issue.web_url == "https://example.atlassian.net/browse/BMS-451"


async def test_get_issue_trims_whitespace_from_the_key() -> None:
    client, handler = make_jira_client(json_responder(ISSUE_PAYLOAD))

    await client.get_issue("  BMS-451  ")

    assert handler.last_request.url.path == "/rest/api/3/issue/BMS-451"


async def test_get_issue_tolerates_an_issue_with_no_links_or_labels() -> None:
    payload = {"id": "1", "key": "X-1", "fields": {"summary": "bare"}}
    client, _ = make_jira_client(json_responder(payload))

    issue = await client.get_issue("X-1")

    assert issue.links == []
    assert issue.labels == []
    assert issue.description == ""
    assert issue.assignee is None


async def test_get_issue_raises_not_found_on_404() -> None:
    client, _ = make_jira_client(json_responder({"errorMessages": ["nope"]}, status_code=404))

    with pytest.raises(ItemNotFoundError):
        await client.get_issue("BMS-999")


async def test_get_issue_raises_not_found_when_payload_is_empty() -> None:
    client, _ = make_jira_client(json_responder({}))

    with pytest.raises(ItemNotFoundError):
        await client.get_issue("BMS-999")


# -- search ------------------------------------------------------------------


async def test_search_maps_issues_and_pagination_token() -> None:
    client, _ = make_jira_client(json_responder(SEARCH_PAYLOAD))

    result = await client.search(jql="project = BMS")

    assert [r.key for r in result.results] == ["BMS-451", "BMS-452"]
    assert result.results[0].status == "In Progress"
    assert result.results[0].assignee == "Dana Ruiz"
    assert result.results[1].assignee is None
    assert result.next_page_token == "tok-page-2"
    assert result.is_last is False
    assert result.jql == "project = BMS"


async def test_search_uses_the_token_paginated_endpoint() -> None:
    """The old /rest/api/3/search is deprecated; we must call /search/jql."""
    client, handler = make_jira_client(json_responder(SEARCH_PAYLOAD))

    await client.search(jql="project = BMS")

    assert handler.last_request.url.path == "/rest/api/3/search/jql"


async def test_search_always_requests_fields() -> None:
    """/search/jql returns only id and key unless fields is supplied."""
    client, handler = make_jira_client(json_responder(SEARCH_PAYLOAD))

    await client.search(jql="project = BMS")

    fields = handler.last_request.url.params["fields"]
    assert "summary" in fields
    assert "status" in fields


async def test_search_sends_the_page_token_when_given() -> None:
    client, handler = make_jira_client(json_responder(SEARCH_PAYLOAD))

    await client.search(jql="project = BMS", next_page_token="tok-page-2")

    assert handler.last_request.url.params["nextPageToken"] == "tok-page-2"


async def test_search_omits_the_page_token_on_a_first_request() -> None:
    client, handler = make_jira_client(json_responder(SEARCH_PAYLOAD))

    await client.search(jql="project = BMS")

    assert "nextPageToken" not in handler.last_request.url.params


@pytest.mark.parametrize(("requested", "expected"), [(999, MAX_PAGE_SIZE), (0, 1), (10, 10)])
async def test_search_clamps_page_size(requested: int, expected: int) -> None:
    client, handler = make_jira_client(json_responder(SEARCH_PAYLOAD))

    await client.search(jql="project = BMS", max_results=requested)

    assert handler.last_request.url.params["maxResults"] == str(expected)


async def test_search_treats_a_missing_token_as_the_last_page() -> None:
    payload = {"issues": []}
    client, _ = make_jira_client(json_responder(payload))

    result = await client.search(jql="project = BMS")

    assert result.next_page_token is None
    assert result.is_last is True


async def test_search_rejects_a_non_list_issues_field() -> None:
    client, _ = make_jira_client(json_responder({"issues": {"key": "X-1"}}))

    with pytest.raises(ConnectorServiceError):
        await client.search(jql="project = BMS")


# -- auth and failures -------------------------------------------------------


async def test_basic_auth_uses_email_and_api_token() -> None:
    client, handler = make_jira_client(json_responder(ISSUE_PAYLOAD))

    await client.get_issue("BMS-451")

    expected = base64.b64encode(b"svc-radia@example.com:tok-secret").decode()
    assert handler.last_request.headers["Authorization"] == f"Basic {expected}"


@pytest.mark.parametrize("status", [401, 403])
async def test_auth_failures_are_auth_errors(status: int) -> None:
    client, _ = make_jira_client(json_responder({}, status_code=status))

    with pytest.raises(ConnectorAuthError):
        await client.get_issue("BMS-451")


async def test_rate_limiting_is_reported_distinctly() -> None:
    """Atlassian rate-limits hard; the message should say so, not 'server error'."""
    client, _ = make_jira_client(json_responder({}, status_code=429))

    with pytest.raises(ConnectorServiceError) as exc_info:
        await client.get_issue("BMS-451")

    assert exc_info.value.status_code == 429
    assert "rate-limited" in str(exc_info.value).lower()


async def test_transport_failure_is_a_service_error() -> None:
    def _boom(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("dns", request=request)

    client, _ = make_jira_client(_boom)

    with pytest.raises(ConnectorServiceError):
        await client.get_issue("BMS-451")


@pytest.mark.parametrize(
    "overrides",
    [{"site_url": ""}, {"email": ""}, {"api_token": ""}],
)
async def test_incomplete_credentials_block_the_request(overrides: dict[str, str]) -> None:
    client, handler = make_jira_client(
        json_responder(ISSUE_PAYLOAD), settings=atlassian_settings(**overrides)
    )

    with pytest.raises(ConnectorNotConfiguredError):
        await client.get_issue("BMS-451")

    assert handler.requests == []
