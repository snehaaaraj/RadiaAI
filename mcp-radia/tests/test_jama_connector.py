"""Unit tests for the Jama connector. All HTTP is mocked; nothing leaves the process."""

import base64
import json

import httpx2
import pytest

from mcp_radia.connectors.errors import (
    ConnectorAuthError,
    ConnectorNotConfiguredError,
    ConnectorServiceError,
    ItemNotFoundError,
)
from mcp_radia.connectors.jama import (
    MAX_PAGE_SIZE,
    JamaClient,
    JamaCredentials,
    JamaLocalCredentials,
    strip_html,
)
from tests.jama_fixtures import (
    CHILDREN_PAYLOAD,
    CREDENTIALS,
    EMPTY_CHILDREN_PAYLOAD,
    ITEM_PAYLOAD,
    PROJECTS_PAYLOAD,
    SEARCH_PAYLOAD,
    TOKEN_PAYLOAD,
    TOP_LEVEL_ITEM_PAYLOAD,
    jama_settings,
    json_responder,
    make_client,
    routed_responder,
)

pytestmark = pytest.mark.unit


# -- settings ----------------------------------------------------------------


def test_rest_base_and_token_url_are_built_from_base_url() -> None:
    settings = jama_settings(base_url="https://example.jamacloud.com/", api_version="v1")

    assert settings.rest_base == "https://example.jamacloud.com/rest/v1"
    assert settings.token_url == "https://example.jamacloud.com/rest/oauth/token"


def test_settings_are_configured_by_base_url_alone() -> None:
    assert jama_settings().is_configured is True
    assert jama_settings(base_url="").is_configured is False


def test_settings_carry_no_credentials() -> None:
    """There is no shared server account: identity is never a server setting."""
    fields = set(jama_settings().model_dump().keys())

    assert fields == {"base_url", "api_version", "timeout_seconds", "verify_ssl"}


@pytest.mark.parametrize(
    ("credentials", "expected"),
    [
        (CREDENTIALS, True),
        (None, False),
        (JamaCredentials(client_id="", client_secret="csecret"), False),
        (JamaCredentials(client_id="cid", client_secret="  "), False),
    ],
)
def test_client_is_configured_only_with_base_url_and_an_account(
    credentials: JamaCredentials | None, expected: bool
) -> None:
    assert JamaClient(jama_settings(), credentials).is_configured is expected
    assert JamaClient(jama_settings(base_url=""), credentials).is_configured is False


def test_with_credentials_keeps_connection_settings_and_swaps_identity() -> None:
    base = JamaClient(jama_settings(api_version="v2", timeout_seconds=5.0))
    other = JamaCredentials(client_id="user-cid", client_secret="user-secret")

    scoped = base.with_credentials(other)

    assert scoped is not base
    assert scoped.settings is base.settings
    assert scoped.credentials == other
    assert base.credentials is None


def test_secret_is_not_in_repr() -> None:
    assert "csecret" not in repr(CREDENTIALS)


def test_local_credentials_need_both_halves() -> None:
    assert JamaLocalCredentials(_env_file=None, client_id="a", client_secret="b").to_credentials() == (
        JamaCredentials(client_id="a", client_secret="b")
    )
    assert JamaLocalCredentials(_env_file=None, client_id="a", client_secret="").to_credentials() is None


# -- html stripping ----------------------------------------------------------


def test_strip_html_converts_markup_to_readable_text() -> None:
    result = strip_html("<p>The battery <b>shall</b> report.</p><p>Accuracy &gt; 98&#37;.</p>")

    assert result == "The battery shall report.\nAccuracy > 98%."


def test_strip_html_handles_breaks_and_empty_values() -> None:
    assert strip_html("line one<br/>line two") == "line one\nline two"
    assert strip_html(None) == ""
    assert strip_html("") == ""


# -- get_item ----------------------------------------------------------------


async def test_get_item_maps_payload_to_model() -> None:
    client, handler = make_client(jama_settings(), json_responder(ITEM_PAYLOAD))

    item = await client.get_item(12345)

    assert item.id == 12345
    assert item.document_key == "SRS-42"
    assert item.global_id == "GID-987"
    assert item.name == "Battery shall report state of charge"
    assert item.status == "Approved"
    assert item.project_id == 7
    assert item.item_type_id == 31
    assert item.modified_date == "2026-02-11T14:30:00.000+0000"
    # Description arrives as HTML and must be flattened to text.
    assert item.description == "The battery shall report state of charge.\nAccuracy > 98%."
    # Custom fields survive, because the digital thread depends on them.
    assert item.fields["customField123"] == "traced-to-JIRA-451"
    assert handler.last_request.url.path == "/rest/v1/items/12345"


async def test_get_item_omits_fields_already_surfaced_as_attributes() -> None:
    """Jama repeats name/description/status inside 'fields'; the copy is dropped.

    description in particular is raw HTML and dominated the payload, so this is
    the difference between a usable response and one that blows a context window.
    """
    client, _ = make_client(jama_settings(), json_responder(ITEM_PAYLOAD))

    item = await client.get_item(12345)

    assert "description" not in item.fields
    assert "name" not in item.fields
    assert "status" not in item.fields
    # The typed attributes still carry the same information.
    assert item.name == "Battery shall report state of charge"
    assert item.status == "Approved"
    assert "state of charge" in item.description


async def test_get_item_keeps_custom_fields() -> None:
    """Dropping duplicates must not touch the custom fields, which nothing else exposes."""
    client, _ = make_client(jama_settings(), json_responder(ITEM_PAYLOAD))

    item = await client.get_item(12345)

    assert item.fields["customField123"] == "traced-to-JIRA-451"


async def test_get_item_drops_the_raw_html_copy_of_the_description() -> None:
    """The HTML never reaches the caller - only the flattened text does."""
    client, _ = make_client(jama_settings(), json_responder(ITEM_PAYLOAD))

    item = await client.get_item(12345)

    assert "<p>" not in json.dumps(item.model_dump())

    client, _ = make_client(jama_settings(), json_responder(ITEM_PAYLOAD))

    item = await client.get_item(12345)

    assert item.web_url == "https://example.jamacloud.com/perspective.req#/items/12345?projectId=7"


async def test_get_item_raises_not_found_on_404() -> None:
    client, _ = make_client(jama_settings(), json_responder({"meta": {}}, status_code=404))

    with pytest.raises(ItemNotFoundError):
        await client.get_item(999)


async def test_get_item_maps_the_document_tree_parent_id() -> None:
    """Jama's location.parent.item is the real containment parent, distinct from
    both children (jama_get_children) and traceability relationships
    (list_related_items) - this must be parsed and exposed, not silently dropped."""
    client, _ = make_client(jama_settings(), json_responder(ITEM_PAYLOAD))

    item = await client.get_item(12345)

    assert item.parent_id == 999


async def test_get_item_parent_id_is_none_for_a_top_level_item() -> None:
    """Jama omits location.parent entirely for a top-level item - that is 'no parent',
    not an error, and must not be confused with the item itself being unreachable."""
    client, _ = make_client(jama_settings(), json_responder(TOP_LEVEL_ITEM_PAYLOAD))

    item = await client.get_item(99999)

    assert item.parent_id is None


async def test_search_results_also_carry_parent_id() -> None:
    """Summaries (search/children/related) use the same raw-item mapping as get_item,
    so parent_id must be consistently available there too, not just on the full item."""
    payload = {
        "meta": {"status": "OK", "pageInfo": {"startIndex": 0, "resultCount": 1, "totalResults": 1}},
        "data": [ITEM_PAYLOAD["data"]],
    }
    client, _ = make_client(jama_settings(), json_responder(payload))

    result = await client.search(query="battery")

    assert result.results[0].parent_id == 999


async def test_get_item_raises_not_found_when_payload_has_no_data() -> None:
    """A 200 with an empty body is still 'not there' from the caller's view."""
    client, _ = make_client(jama_settings(), json_responder({"meta": {"status": "OK"}}))

    with pytest.raises(ItemNotFoundError):
        await client.get_item(999)


@pytest.mark.parametrize("status", [401, 403])
async def test_auth_failures_are_reported_as_auth_errors(status: int) -> None:
    client, _ = make_client(jama_settings(), json_responder({}, status_code=status))

    with pytest.raises(ConnectorAuthError) as exc_info:
        await client.get_item(1)

    assert exc_info.value.status_code == status


async def test_server_errors_are_reported_as_service_errors() -> None:
    client, _ = make_client(jama_settings(), json_responder({}, status_code=500))

    with pytest.raises(ConnectorServiceError) as exc_info:
        await client.get_item(1)

    assert exc_info.value.status_code == 500


async def test_transport_failures_are_reported_as_service_errors() -> None:
    def _boom(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("no route to host", request=request)

    client, _ = make_client(jama_settings(), _boom)

    with pytest.raises(ConnectorServiceError):
        await client.get_item(1)


async def test_non_json_response_is_reported_as_a_service_error() -> None:
    def _html(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, text="<html>maintenance</html>", request=request)

    client, _ = make_client(jama_settings(), _html)

    with pytest.raises(ConnectorServiceError):
        await client.get_item(1)


async def test_unconfigured_client_fails_without_making_a_request() -> None:
    client, handler = make_client(
        jama_settings(base_url=""), json_responder(ITEM_PAYLOAD), auto_token=False
    )

    with pytest.raises(ConnectorNotConfiguredError, match="JAMA_BASE_URL"):
        await client.get_item(1)

    assert handler.requests == [], "must not call out with no base URL"


async def test_client_without_an_account_asks_the_user_to_link_one() -> None:
    client, handler = make_client(
        jama_settings(), json_responder(ITEM_PAYLOAD), credentials=None, auto_token=False
    )

    with pytest.raises(ConnectorNotConfiguredError, match="Link your Jama account"):
        await client.get_item(1)

    assert handler.requests == [], "must not call out with no account"


# -- search ------------------------------------------------------------------


async def test_search_maps_results_and_paging_metadata() -> None:
    client, _ = make_client(jama_settings(), json_responder(SEARCH_PAYLOAD))

    result = await client.search(query="battery")

    assert [r.id for r in result.results] == [12345, 12346]
    assert result.results[0].document_key == "SRS-42"
    assert result.results[0].name == "Battery shall report state of charge"
    # totalResults, not the length of this page - paging depends on it.
    assert result.total == 137
    assert result.start_at == 0


async def test_search_sends_filters_as_query_parameters() -> None:
    client, handler = make_client(jama_settings(), json_responder(SEARCH_PAYLOAD))

    await client.search(query="battery", project_id=7, item_type_id=31, start_at=50)

    params = handler.last_request.url.params
    assert handler.last_request.url.path == "/rest/v1/abstractitems"
    assert params["contains"] == "battery"
    assert params["project"] == "7"
    assert params["itemType"] == "31"
    assert params["startAt"] == "50"


async def test_search_omits_filters_that_were_not_supplied() -> None:
    client, handler = make_client(jama_settings(), json_responder(SEARCH_PAYLOAD))

    await client.search()

    params = handler.last_request.url.params
    assert "contains" not in params
    assert "project" not in params
    assert "itemType" not in params


@pytest.mark.parametrize(
    ("requested", "expected"),
    [(999, MAX_PAGE_SIZE), (0, 1), (-5, 1), (10, 10)],
)
async def test_search_clamps_page_size_to_what_jama_accepts(requested: int, expected: int) -> None:
    """Jama rejects maxResults above 50, so the connector clamps rather than erroring."""
    client, handler = make_client(jama_settings(), json_responder(SEARCH_PAYLOAD))

    result = await client.search(max_results=requested)

    assert handler.last_request.url.params["maxResults"] == str(expected)
    assert result.max_results == expected


async def test_search_falls_back_to_page_length_when_metadata_is_missing() -> None:
    payload = {"data": SEARCH_PAYLOAD["data"]}
    client, _ = make_client(jama_settings(), json_responder(payload))

    result = await client.search()

    assert result.total == 2


async def test_search_rejects_a_non_list_data_field() -> None:
    client, _ = make_client(jama_settings(), json_responder({"data": {"id": 1}}))

    with pytest.raises(ConnectorServiceError):
        await client.search()


# -- projects (name -> numeric id resolution) --------------------------------


async def test_list_projects_maps_results() -> None:
    client, handler = make_client(jama_settings(), json_responder(PROJECTS_PAYLOAD))

    projects = await client.list_projects()

    assert [p.id for p in projects] == [7, 42]
    assert projects[1].project_key == "SAND"
    assert projects[1].name == "Sandbox"
    assert handler.last_request.url.path == "/rest/v1/projects"


async def test_list_projects_rejects_a_non_list_data_field() -> None:
    client, _ = make_client(jama_settings(), json_responder({"data": {"id": 1}}))

    with pytest.raises(ConnectorServiceError):
        await client.list_projects()


async def test_list_projects_clamps_page_size_to_what_jama_accepts() -> None:
    client, handler = make_client(jama_settings(), json_responder(PROJECTS_PAYLOAD))

    await client.list_projects(max_results=500)

    assert handler.last_request.url.params["maxResults"] == str(MAX_PAGE_SIZE)


# -- children (containment hierarchy) ----------------------------------------


async def test_get_children_maps_results_and_paging_metadata() -> None:
    client, _ = make_client(jama_settings(), json_responder(CHILDREN_PAYLOAD))

    result = await client.get_children(12345)

    assert result.parent_id == 12345
    assert [r.id for r in result.results] == [22001, 22002]
    assert result.results[0].document_key == "SRS-101"
    assert result.results[0].name == "Cell voltage shall be sampled every 100 ms"
    # totalResults, not this page's length: there are more children than returned.
    assert result.total == 9
    assert result.start_at == 0


async def test_get_children_calls_the_children_endpoint() -> None:
    client, handler = make_client(jama_settings(), json_responder(CHILDREN_PAYLOAD))

    await client.get_children(12345)

    assert handler.last_request.url.path == "/rest/v1/items/12345/children"


async def test_get_children_sends_paging_parameters() -> None:
    client, handler = make_client(jama_settings(), json_responder(CHILDREN_PAYLOAD))

    await client.get_children(12345, start_at=50, max_results=10)

    params = handler.last_request.url.params
    assert params["startAt"] == "50"
    assert params["maxResults"] == "10"


@pytest.mark.parametrize(
    ("requested", "expected"),
    [(999, MAX_PAGE_SIZE), (0, 1), (-5, 1), (10, 10)],
)
async def test_get_children_clamps_page_size_like_search(requested: int, expected: int) -> None:
    client, handler = make_client(jama_settings(), json_responder(CHILDREN_PAYLOAD))

    result = await client.get_children(12345, max_results=requested)

    assert handler.last_request.url.params["maxResults"] == str(expected)
    assert result.max_results == expected


async def test_get_children_returns_empty_for_an_item_with_no_children() -> None:
    """A leaf requirement is normal, not an error."""
    client, _ = make_client(jama_settings(), json_responder(EMPTY_CHILDREN_PAYLOAD))

    result = await client.get_children(12345)

    assert result.results == []
    assert result.total == 0


async def test_get_children_reports_a_missing_parent_as_not_found() -> None:
    client, _ = make_client(jama_settings(), json_responder({"meta": {}}, status_code=404))

    with pytest.raises(ItemNotFoundError):
        await client.get_children(999)


async def test_get_children_falls_back_to_page_length_when_metadata_is_missing() -> None:
    payload = {"data": CHILDREN_PAYLOAD["data"]}
    client, _ = make_client(jama_settings(), json_responder(payload))

    result = await client.get_children(12345)

    assert result.total == 2


async def test_get_children_rejects_a_non_list_data_field() -> None:
    client, _ = make_client(jama_settings(), json_responder({"data": {"id": 1}}))

    with pytest.raises(ConnectorServiceError):
        await client.get_children(12345)


async def test_get_children_does_not_recurse_into_grandchildren() -> None:
    """One level, one page: a single call must make exactly one request."""
    client, handler = make_client(jama_settings(), json_responder(CHILDREN_PAYLOAD))

    await client.get_children(12345)

    assert len(handler.requests) == 1


# -- authentication ----------------------------------------------------------


def _token_client(responder):  # type: ignore[no-untyped-def]
    """A client whose token exchange is visible to the test, not auto-answered."""
    return make_client(jama_settings(), responder, auto_token=False)


async def test_oauth_fetches_a_token_then_uses_it_as_a_bearer() -> None:
    client, handler = _token_client(
        routed_responder(
            {"/rest/oauth/token": (200, TOKEN_PAYLOAD), "/items/": (200, ITEM_PAYLOAD)}
        ),
    )

    await client.get_item(12345)

    token_request, item_request = handler.requests
    assert token_request.url.path == "/rest/oauth/token"
    assert token_request.method == "POST"
    assert item_request.headers["Authorization"] == "Bearer tok-abc123"


async def test_token_request_authenticates_as_the_individual_account() -> None:
    client, handler = _token_client(
        routed_responder(
            {"/rest/oauth/token": (200, TOKEN_PAYLOAD), "/items/": (200, ITEM_PAYLOAD)}
        ),
    )

    await client.get_item(12345)

    expected = base64.b64encode(b"cid:csecret").decode()
    assert handler.requests[0].headers["Authorization"] == f"Basic {expected}"


async def test_oauth_token_is_reused_across_calls() -> None:
    """A second call must not re-authenticate; the token is cached until expiry."""
    client, handler = _token_client(
        routed_responder(
            {"/rest/oauth/token": (200, TOKEN_PAYLOAD), "/items/": (200, ITEM_PAYLOAD)}
        ),
    )

    await client.get_item(12345)
    await client.get_item(12345)

    token_requests = [r for r in handler.requests if r.url.path == "/rest/oauth/token"]
    assert len(token_requests) == 1


async def test_oauth_token_rejection_is_an_auth_error() -> None:
    client, _ = _token_client(
        routed_responder({"/rest/oauth/token": (401, {"error": "invalid_client"})}),
    )

    with pytest.raises(ConnectorAuthError) as exc_info:
        await client.get_item(1)

    assert exc_info.value.operation == "oauth_token"


async def test_oauth_response_without_a_token_is_a_service_error() -> None:
    client, _ = _token_client(
        routed_responder({"/rest/oauth/token": (200, {"expires_in": 3600})}),
    )

    with pytest.raises(ConnectorServiceError):
        await client.get_item(1)


async def test_concurrent_calls_share_a_single_token_request() -> None:
    """The refresh lock must stop a thundering herd of token requests at startup."""
    import asyncio

    client, handler = _token_client(
        routed_responder(
            {"/rest/oauth/token": (200, TOKEN_PAYLOAD), "/items/": (200, ITEM_PAYLOAD)}
        ),
    )

    await asyncio.gather(*(client.get_item(12345) for _ in range(5)))

    token_requests = [r for r in handler.requests if r.url.path == "/rest/oauth/token"]
    assert len(token_requests) == 1


# -- relationships (used by cross-system linking) ----------------------------

RELATED_PAYLOAD = {
    "data": [{"id": 999, "documentKey": "SRS-99", "project": 7, "fields": {"name": "Parent req"}}]
}


async def test_get_related_items_queries_both_directions() -> None:
    client, handler = make_client(jama_settings(), json_responder(RELATED_PAYLOAD))

    related = await client.get_related_items(12345)

    paths = [r.url.path for r in handler.requests]
    assert "/rest/v1/items/12345/upstreamrelated" in paths
    assert "/rest/v1/items/12345/downstreamrelated" in paths
    assert {link.direction for link in related} == {"upstream", "downstream"}


async def test_get_related_items_maps_the_far_end() -> None:
    client, _ = make_client(jama_settings(), json_responder(RELATED_PAYLOAD))

    related = await client.get_related_items(12345)

    assert related[0].item.document_key == "SRS-99"
    assert related[0].item.name == "Parent req"
    assert related[0].item.web_url is not None


async def test_get_related_items_is_empty_when_nothing_is_linked() -> None:
    client, _ = make_client(jama_settings(), json_responder({"data": []}))

    assert await client.get_related_items(12345) == []


async def test_get_related_items_tolerates_a_malformed_direction() -> None:
    """One bad half must not lose the other half's links."""

    def _respond(request: httpx2.Request) -> httpx2.Response:
        if "upstreamrelated" in request.url.path:
            return httpx2.Response(200, json={"data": "nonsense"}, request=request)
        return httpx2.Response(200, json=RELATED_PAYLOAD, request=request)

    client, _ = make_client(jama_settings(), _respond)

    related = await client.get_related_items(12345)

    assert [link.direction for link in related] == ["downstream"]
