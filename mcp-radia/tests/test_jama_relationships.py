"""Paginated Jama traceability through both desktop and HTTP-facing tool registries."""

import httpx2
import pytest

from mcp_radia import desktop
from mcp_radia.config import ServerSettings
from mcp_radia.connectors.errors import ConnectorServiceError
from mcp_radia.server import build_server
from tests.conftest import connected_client
from tests.jama_fixtures import jama_settings, json_responder, make_client

pytestmark = pytest.mark.unit


def relationship_page(start=0, total=53, count=3):
    return {
        "meta": {"pageInfo": {"startIndex": start, "totalResults": total}},
        "data": [
            {
                "id": 1000 + start + index,
                "documentKey": f"SRS-{1000 + start + index}",
                "project": 7,
                "fields": {"name": f"Related requirement {start + index}"},
            }
            for index in range(count)
        ],
    }


@pytest.mark.parametrize("direction", ["upstream", "downstream"])
async def test_connector_pages_relationships_with_real_total(direction):
    client, handler = make_client(jama_settings(), json_responder(relationship_page(start=50)))
    page = await client.get_relationships(12345, direction=direction, start_at=50, max_results=10)
    assert page.item_id == 12345
    assert page.direction == direction
    assert page.total == 53
    assert page.start_at == 50
    assert page.max_results == 10
    assert page.next_start_at is None
    assert [item.id for item in page.results] == [1050, 1051, 1052]
    assert page.results[0].web_url
    request = handler.last_request
    assert request.method == "GET"
    assert request.url.path == f"/rest/v1/items/12345/{direction}related"
    assert request.url.params["startAt"] == "50"
    assert request.url.params["maxResults"] == "10"


async def test_connector_reports_next_page_instead_of_truncating():
    client, _ = make_client(jama_settings(), json_responder(relationship_page(count=50)))
    page = await client.get_relationships(12345, direction="downstream")
    assert len(page.results) == 50
    assert page.total == 53
    assert page.next_start_at == 50


@pytest.mark.parametrize("count,expected_next", [(0, None), (1, None), (2, 2)])
async def test_connector_does_not_invent_total_when_metadata_is_absent(count, expected_next):
    client, _ = make_client(
        jama_settings(), json_responder({"data": relationship_page(count=count)["data"]})
    )
    page = await client.get_relationships(12345, direction="upstream", max_results=2)
    assert page.total is None
    assert page.next_start_at == expected_next


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": None},
        {"data": "invalid"},
        {"data": [None]},
        {"data": [], "meta": {"pageInfo": {"totalResults": "10"}}},
        {"data": [], "meta": {"pageInfo": {"totalResults": -1}}},
        {"data": [], "meta": {"pageInfo": "invalid"}},
        {"data": [], "meta": "invalid"},
        {"data": [], "meta": {"pageInfo": {"startIndex": 10}}},
        {"data": [], "meta": {"pageInfo": {"totalResults": 10}}},
    ],
)
async def test_malformed_relationship_data_never_looks_like_no_links(payload):
    client, _ = make_client(jama_settings(), json_responder(payload))
    with pytest.raises(ConnectorServiceError):
        await client.get_relationships(12345, direction="upstream")


@pytest.fixture(params=["desktop", "http-registry"])
def relationship_server(request, monkeypatch):
    def respond(http_request):
        start = int(http_request.url.params["startAt"])
        count = min(int(http_request.url.params["maxResults"]), 53 - start)
        return httpx2.Response(200, json=relationship_page(start=start, count=count))

    client, handler = make_client(jama_settings(), respond)
    if request.param == "desktop":
        monkeypatch.setenv("JAMA_BASE_URL", "https://example.jamacloud.com")
        monkeypatch.setenv("JAMA_CLIENT_ID", "desktop-test-client")
        monkeypatch.setenv("JAMA_CLIENT_SECRET", "desktop-test-secret")
        monkeypatch.setattr(desktop, "JamaClient", lambda *args: client)
        server = desktop.build_desktop_server()
    else:
        server = build_server(
            ServerSettings(_env_file=None, environment="test"), jama_client=client
        )
    return server, handler


@pytest.mark.parametrize("direction", ["upstream", "downstream"])
async def test_relationship_tool_reads_both_pages_on_both_surfaces(relationship_server, direction):
    server, handler = relationship_server
    async with connected_client(server) as session:
        first = await session.call_tool(
            "jama_get_relationships", {"item_id": 12345, "direction": direction}
        )
        assert not first.is_error
        page = first.structured_content
        assert page["next_start_at"] == 50
        second = await session.call_tool(
            "jama_get_relationships",
            {"item_id": 12345, "direction": direction, "start_at": page["next_start_at"]},
        )
    assert not second.is_error
    last = second.structured_content
    assert last["next_start_at"] is None
    assert last["total"] == 53
    assert len(page["results"]) + len(last["results"]) == 53
    assert all(r.url.path.endswith(f"/{direction}related") for r in handler.requests)


@pytest.mark.parametrize(
    "arguments",
    [
        {"item_id": 1},
        {"item_id": 1, "direction": "both"},
        {"item_id": 0, "direction": "upstream"},
        {"item_id": 1, "direction": "downstream", "start_at": -1},
        {"item_id": 1, "direction": "upstream", "max_results": 51},
    ],
)
async def test_invalid_relationship_calls_never_reach_jama(relationship_server, arguments):
    server, handler = relationship_server
    async with connected_client(server) as session:
        result = await session.call_tool("jama_get_relationships", arguments)
    assert result.is_error
    assert handler.requests == []


async def test_relationship_tool_requires_linked_account_over_http():
    client, handler = make_client(
        jama_settings(), json_responder(relationship_page()), credentials=None
    )
    server = build_server(ServerSettings(_env_file=None, environment="test"), jama_client=client)
    async with connected_client(server) as session:
        result = await session.call_tool(
            "jama_get_relationships", {"item_id": 12345, "direction": "upstream"}
        )
    assert result.is_error
    assert "Link your Jama account" in str(result.content)
    assert handler.requests == []


async def test_relationship_permission_failure_is_not_an_empty_list():
    client, _ = make_client(jama_settings(), json_responder({}, status_code=403))
    server = build_server(ServerSettings(_env_file=None, environment="test"), jama_client=client)
    async with connected_client(server) as session:
        result = await session.call_tool(
            "jama_get_relationships", {"item_id": 12345, "direction": "downstream"}
        )
    assert result.is_error
