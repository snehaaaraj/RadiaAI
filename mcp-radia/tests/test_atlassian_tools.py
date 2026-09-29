"""Tests for the Jira and Confluence MCP tools, over a real MCP client session."""

from collections.abc import Callable

import httpx2
import pytest

from mcp_radia.config import ServerSettings
from mcp_radia.connectors.atlassian import AtlassianSettings
from mcp_radia.server import build_server
from tests.atlassian_fixtures import (
    ISSUE_PAYLOAD,
    PAGE_PAYLOAD,
    SEARCH_PAYLOAD,
    SEARCH_RESULTS_PAYLOAD,
    atlassian_settings,
    make_confluence_client,
    make_jira_client,
)
from tests.conftest import connected_client
from tests.jama_fixtures import RecordingHandler, json_responder

pytestmark = pytest.mark.unit

Responder = Callable[[httpx2.Request], httpx2.Response]


def _server_with(
    jira_responder: Responder,
    confluence_responder: Responder,
    settings: AtlassianSettings | None = None,
) -> tuple[object, RecordingHandler, RecordingHandler]:
    jira_client, jira_handler = make_jira_client(jira_responder, settings)
    confluence_client, confluence_handler = make_confluence_client(confluence_responder, settings)
    server = build_server(
        ServerSettings(_env_file=None, environment="test"),
        jira_client=jira_client,
        confluence_client=confluence_client,
    )
    return server, jira_handler, confluence_handler


async def test_all_six_tools_are_advertised() -> None:
    server, _, _ = _server_with(json_responder(ISSUE_PAYLOAD), json_responder(PAGE_PAYLOAD))

    async with connected_client(server) as session:
        names = {t.name for t in (await session.list_tools()).tools}

    assert names == {
        "jama_get_item",
        "jama_search",
        "jira_get_issue",
        "jira_search",
        "confluence_get_page",
        "confluence_search",
    }


async def test_every_tool_is_read_only() -> None:
    server, _, _ = _server_with(json_responder(ISSUE_PAYLOAD), json_responder(PAGE_PAYLOAD))

    async with connected_client(server) as session:
        tools = (await session.list_tools()).tools

    for tool in tools:
        assert tool.annotations is not None, tool.name
        assert tool.annotations.read_only_hint is True, tool.name
        assert tool.annotations.destructive_hint is False, tool.name


async def test_jira_get_issue_returns_structured_content() -> None:
    server, jira, _ = _server_with(json_responder(ISSUE_PAYLOAD), json_responder(PAGE_PAYLOAD))

    async with connected_client(server) as session:
        result = await session.call_tool("jira_get_issue", {"issue_key": "BMS-451"})

    assert not result.is_error
    assert result.structured_content is not None
    assert result.structured_content["key"] == "BMS-451"
    assert result.structured_content["status"] == "In Progress"
    assert len(result.structured_content["links"]) == 2
    assert jira.last_request.url.path == "/rest/api/3/issue/BMS-451"


async def test_jira_search_requires_jql() -> None:
    server, _, _ = _server_with(json_responder(SEARCH_PAYLOAD), json_responder(PAGE_PAYLOAD))

    async with connected_client(server) as session:
        tools = {t.name: t for t in (await session.list_tools()).tools}

    assert tools["jira_search"].input_schema["required"] == ["jql"]


async def test_jira_search_passes_jql_through() -> None:
    server, jira, _ = _server_with(json_responder(SEARCH_PAYLOAD), json_responder(PAGE_PAYLOAD))

    async with connected_client(server) as session:
        result = await session.call_tool("jira_search", {"jql": "project = BMS", "max_results": 10})

    assert not result.is_error
    assert jira.last_request.url.params["jql"] == "project = BMS"
    assert jira.last_request.url.params["maxResults"] == "10"
    assert result.structured_content is not None
    assert result.structured_content["next_page_token"] == "tok-page-2"


async def test_confluence_get_page_returns_flattened_body() -> None:
    server, _, conf = _server_with(json_responder(ISSUE_PAYLOAD), json_responder(PAGE_PAYLOAD))

    async with connected_client(server) as session:
        result = await session.call_tool("confluence_get_page", {"page_id": "123456789"})

    assert not result.is_error
    assert result.structured_content is not None
    assert "Thermal limits are defined in SRS-42." in result.structured_content["body"]
    assert conf.last_request.url.params["body-format"] == "storage"


async def test_confluence_search_builds_cql_from_simple_filters() -> None:
    server, _, conf = _server_with(
        json_responder(ISSUE_PAYLOAD), json_responder(SEARCH_RESULTS_PAYLOAD)
    )

    async with connected_client(server) as session:
        result = await session.call_tool(
            "confluence_search", {"query": "thermal", "space_key": "ENG"}
        )

    assert not result.is_error
    assert conf.last_request.url.params["cql"] == 'text ~ "thermal" AND space = "ENG"'


async def test_confluence_search_accepts_no_arguments() -> None:
    server, _, _ = _server_with(
        json_responder(ISSUE_PAYLOAD), json_responder(SEARCH_RESULTS_PAYLOAD)
    )

    async with connected_client(server) as session:
        result = await session.call_tool("confluence_search", {})

    assert not result.is_error


async def test_a_missing_jira_issue_becomes_a_tool_error() -> None:
    server, _, _ = _server_with(json_responder({}, status_code=404), json_responder(PAGE_PAYLOAD))

    async with connected_client(server) as session:
        result = await session.call_tool("jira_get_issue", {"issue_key": "NOPE-1"})

    assert result.is_error


async def test_unconfigured_atlassian_names_the_variables_to_set() -> None:
    server, _, _ = _server_with(
        json_responder(ISSUE_PAYLOAD),
        json_responder(PAGE_PAYLOAD),
        settings=atlassian_settings(site_url=""),
    )

    async with connected_client(server) as session:
        result = await session.call_tool("jira_get_issue", {"issue_key": "BMS-451"})

    assert result.is_error
    assert "ATLASSIAN_SITE_URL" in str(result.content)


async def test_oversized_jira_page_size_is_rejected_before_the_call() -> None:
    server, jira, _ = _server_with(json_responder(SEARCH_PAYLOAD), json_responder(PAGE_PAYLOAD))

    async with connected_client(server) as session:
        result = await session.call_tool("jira_search", {"jql": "x", "max_results": 5000})

    assert result.is_error
    assert jira.requests == []
