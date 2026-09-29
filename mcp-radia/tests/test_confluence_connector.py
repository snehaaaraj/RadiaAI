"""Unit tests for the Confluence Cloud connector. All HTTP is mocked."""

import pytest

from mcp_radia.connectors.confluence import MAX_PAGE_SIZE, escape_cql_value
from mcp_radia.connectors.errors import (
    ConnectorNotConfiguredError,
    ConnectorServiceError,
    ItemNotFoundError,
)
from tests.atlassian_fixtures import (
    PAGE_PAYLOAD,
    SEARCH_RESULTS_PAYLOAD,
    atlassian_settings,
    make_confluence_client,
)
from tests.jama_fixtures import json_responder

pytestmark = pytest.mark.unit


# -- get_page ----------------------------------------------------------------


async def test_get_page_maps_payload_to_model() -> None:
    client, handler = make_confluence_client(json_responder(PAGE_PAYLOAD))

    page = await client.get_page("123456789")

    assert page.id == "123456789"
    assert page.title == "Battery Thermal Design"
    assert page.space_id == "555"
    assert page.status == "current"
    assert page.version == 7
    assert page.version_created_at == "2026-02-10T09:00:00Z"
    assert page.author_id == "acc-1"
    assert handler.last_request.url.path == "/wiki/api/v2/pages/123456789"


async def test_get_page_uses_the_v2_body_format_parameter() -> None:
    """v2 ignores the v1 'expand=body.storage' idiom and returns an empty body."""
    client, handler = make_confluence_client(json_responder(PAGE_PAYLOAD))

    await client.get_page("123456789")

    assert handler.last_request.url.params["body-format"] == "storage"
    assert "expand" not in handler.last_request.url.params


async def test_get_page_flattens_storage_xhtml_to_text() -> None:
    client, _ = make_confluence_client(json_responder(PAGE_PAYLOAD))

    page = await client.get_page("123456789")

    assert "Thermal limits are defined in SRS-42." in page.body
    assert "Upper bound 45C" in page.body
    # List items must not run together into one line.
    assert "Upper bound 45C\nLower bound -20C" in page.body
    # <style> content is markup machinery, not prose.
    assert "color:red" not in page.body
    assert "<" not in page.body


async def test_get_page_builds_an_absolute_web_url() -> None:
    client, _ = make_confluence_client(json_responder(PAGE_PAYLOAD))

    page = await client.get_page("123456789")

    assert page.web_url == (
        "https://example.atlassian.net/wiki/spaces/ENG/pages/123456789/Battery+Thermal+Design"
    )


async def test_get_page_tolerates_a_page_with_no_body() -> None:
    payload = {"id": "1", "title": "Stub", "version": {"number": 1}}
    client, _ = make_confluence_client(json_responder(payload))

    page = await client.get_page("1")

    assert page.body == ""
    assert page.web_url is None


async def test_get_page_raises_not_found_on_404() -> None:
    client, _ = make_confluence_client(json_responder({}, status_code=404))

    with pytest.raises(ItemNotFoundError):
        await client.get_page("404404")


async def test_get_page_raises_not_found_when_payload_has_no_id() -> None:
    client, _ = make_confluence_client(json_responder({"results": []}))

    with pytest.raises(ItemNotFoundError):
        await client.get_page("404404")


# -- CQL construction --------------------------------------------------------


def test_escape_cql_value_neutralises_quotes_and_backslashes() -> None:
    assert escape_cql_value('a"b') == 'a\\"b'
    assert escape_cql_value("a\\b") == "a\\\\b"


async def test_build_cql_combines_filters() -> None:
    client, _ = make_confluence_client(json_responder(SEARCH_RESULTS_PAYLOAD))

    cql = client.build_cql(query="thermal", space_key="ENG", content_type="page")

    assert cql == 'text ~ "thermal" AND space = "ENG" AND type = "page"'


async def test_build_cql_escapes_free_text() -> None:
    """A quote in user text must not be able to change the query's meaning."""
    client, _ = make_confluence_client(json_responder(SEARCH_RESULTS_PAYLOAD))

    cql = client.build_cql(query='thermal" OR type = "blogpost')

    assert cql == 'text ~ "thermal\\" OR type = \\"blogpost"'


async def test_build_cql_defaults_to_pages_when_given_nothing() -> None:
    client, _ = make_confluence_client(json_responder(SEARCH_RESULTS_PAYLOAD))

    assert client.build_cql() == 'type = "page"'


async def test_raw_cql_overrides_the_simple_filters() -> None:
    client, handler = make_confluence_client(json_responder(SEARCH_RESULTS_PAYLOAD))

    await client.search(query="ignored", cql="label = urgent")

    assert handler.last_request.url.params["cql"] == "label = urgent"


# -- search ------------------------------------------------------------------


async def test_search_uses_the_v1_cql_endpoint() -> None:
    """CQL search has no v2 equivalent, so v1 is the only option."""
    client, handler = make_confluence_client(json_responder(SEARCH_RESULTS_PAYLOAD))

    await client.search(query="thermal")

    assert handler.last_request.url.path == "/wiki/rest/api/search"


async def test_search_maps_hits_and_totals() -> None:
    client, _ = make_confluence_client(json_responder(SEARCH_RESULTS_PAYLOAD))

    result = await client.search(query="thermal")

    assert [hit.id for hit in result.results] == ["123456789", "987654321"]
    assert result.results[0].type == "page"
    assert result.results[0].space_key == "ENG"
    assert result.total == 42
    assert result.cql == 'text ~ "thermal"'


async def test_search_strips_highlight_markers_from_excerpts() -> None:
    """Confluence wraps matches in @@@hl@@@, which is noise to a model."""
    client, _ = make_confluence_client(json_responder(SEARCH_RESULTS_PAYLOAD))

    result = await client.search(query="thermal")

    assert result.results[0].excerpt == "Thermal limits are defined in SRS-42."


async def test_search_recovers_space_key_from_the_container_url() -> None:
    """The second fixture hit has no content.space, only a container displayUrl."""
    client, _ = make_confluence_client(json_responder(SEARCH_RESULTS_PAYLOAD))

    result = await client.search(query="thermal")

    assert result.results[1].space_key == "ENG"


@pytest.mark.parametrize(("requested", "expected"), [(999, MAX_PAGE_SIZE), (0, 1), (10, 10)])
async def test_search_clamps_page_size(requested: int, expected: int) -> None:
    client, handler = make_confluence_client(json_responder(SEARCH_RESULTS_PAYLOAD))

    result = await client.search(query="thermal", limit=requested)

    assert handler.last_request.url.params["limit"] == str(expected)
    assert result.limit == expected


async def test_search_passes_the_start_offset() -> None:
    client, handler = make_confluence_client(json_responder(SEARCH_RESULTS_PAYLOAD))

    await client.search(query="thermal", start=25)

    assert handler.last_request.url.params["start"] == "25"


async def test_search_rejects_a_non_list_results_field() -> None:
    client, _ = make_confluence_client(json_responder({"results": {"id": 1}}))

    with pytest.raises(ConnectorServiceError):
        await client.search(query="x")


async def test_unconfigured_client_does_not_call_out() -> None:
    client, handler = make_confluence_client(
        json_responder(PAGE_PAYLOAD), settings=atlassian_settings(site_url="")
    )

    with pytest.raises(ConnectorNotConfiguredError):
        await client.get_page("1")

    assert handler.requests == []
