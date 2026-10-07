"""Tests for cross-system linking. All HTTP is mocked."""

import httpx2
import pytest

from mcp_radia.connectors.confluence import ConfluenceClient
from mcp_radia.connectors.genesys import GenesysClient, GenesysSettings
from mcp_radia.connectors.jama import JamaClient
from mcp_radia.connectors.jira import JiraClient
from mcp_radia.linking.references import extract_candidate_keys, texts_from_mapping
from mcp_radia.linking.service import MAX_TEXT_LOOKUPS, LinkingService
from tests.atlassian_fixtures import ISSUE_PAYLOAD, PAGE_PAYLOAD, atlassian_settings
from tests.jama_fixtures import ITEM_PAYLOAD, RecordingHandler, basic_settings

pytestmark = pytest.mark.unit


# -- key extraction ----------------------------------------------------------


def test_extract_finds_jira_and_jama_style_keys() -> None:
    text = "Implements SRS-42 and is blocked by BMS-451."

    assert extract_candidate_keys(text) == ["SRS-42", "BMS-451"]


def test_extract_preserves_first_seen_order_and_deduplicates() -> None:
    assert extract_candidate_keys("BMS-451 then SRS-42 then BMS-451") == ["BMS-451", "SRS-42"]


def test_extract_drops_the_items_own_key() -> None:
    """An item naming itself in its own description is not a relationship."""
    assert extract_candidate_keys("BMS-451 relates to SRS-42", exclude="BMS-451") == ["SRS-42"]


@pytest.mark.parametrize(
    "text",
    ["encoded as UTF-8", "per ISO-26262 guidance", "timestamps are ISO-8601", "see DO-178 B"],
)
def test_extract_ignores_standards_that_look_like_keys(text: str) -> None:
    assert extract_candidate_keys(text) == []


@pytest.mark.parametrize("text", ["lower-1", "a-1", "well-known", "2026-01-05"])
def test_extract_ignores_things_that_are_not_key_shaped(text: str) -> None:
    assert extract_candidate_keys(text) == []


def test_extract_scans_across_several_texts() -> None:
    assert extract_candidate_keys("BMS-451", None, "SRS-42") == ["BMS-451", "SRS-42"]


def test_texts_from_mapping_keeps_only_non_empty_strings() -> None:
    values = {"a": "traced to BMS-451", "b": 7, "c": "", "d": None, "e": {"x": 1}}

    assert texts_from_mapping(values) == ["traced to BMS-451"]


# -- service wiring ----------------------------------------------------------

JAMA_RELATED_PAYLOAD = {
    "data": [
        {
            "id": 999,
            "documentKey": "SRS-99",
            "project": 7,
            "fields": {"name": "Parent requirement"},
        }
    ]
}

CONFLUENCE_PAGE_WITH_LINKS = {
    **PAGE_PAYLOAD,
    "body": {
        "storage": {
            "value": (
                '<p>Implements <ac:link><ri:page ri:content-title="Thermal Spec" '
                'ri:space-key="ENG"/></ac:link> and tracks BMS-451.</p>'
            ),
            "representation": "storage",
        }
    },
}


def _service(
    *,
    jira_routes: dict[str, tuple[int, object]] | None = None,
    jama_routes: dict[str, tuple[int, object]] | None = None,
    confluence_payload: object = None,
    jama_configured: bool = True,
) -> tuple[LinkingService, dict[str, RecordingHandler]]:
    """Build a LinkingService whose connectors all speak to mock transports."""

    def _router(routes: dict[str, tuple[int, object]]) -> RecordingHandler:
        ordered = sorted(routes.items(), key=lambda kv: len(kv[0]), reverse=True)

        def _respond(request: httpx2.Request) -> httpx2.Response:
            for fragment, (status, payload) in ordered:
                if fragment in request.url.path:
                    return httpx2.Response(status, json=payload, request=request)
            return httpx2.Response(404, json={}, request=request)

        return RecordingHandler(_respond)

    jira_handler = _router(jira_routes or {"/issue/": (200, ISSUE_PAYLOAD)})
    jama_handler = _router(
        jama_routes
        or {
            "related": (200, JAMA_RELATED_PAYLOAD),
            "/items/": (200, ITEM_PAYLOAD),
            "abstractitems": (200, {"data": []}),
        }
    )
    confluence_handler = _router({"/pages/": (200, confluence_payload or PAGE_PAYLOAD)})

    def _client(handler: RecordingHandler) -> httpx2.AsyncClient:
        return httpx2.AsyncClient(transport=httpx2.MockTransport(handler))

    jama_settings = basic_settings() if jama_configured else basic_settings(base_url="")
    service = LinkingService(
        jama=JamaClient(jama_settings, client=_client(jama_handler)),
        jira=JiraClient(atlassian_settings(), client=_client(jira_handler)),
        confluence=ConfluenceClient(atlassian_settings(), client=_client(confluence_handler)),
        genesys=GenesysClient(GenesysSettings(_env_file=None)),
    )
    return service, {
        "jira": jira_handler,
        "jama": jama_handler,
        "confluence": confluence_handler,
    }


# -- jira --------------------------------------------------------------------


async def test_jira_native_links_become_related_items() -> None:
    service, _ = _service()

    result = await service.list_related_items("jira", "BMS-451")

    assert result.system == "jira"
    assert result.item_title == "Cell balancing fails at high temperature"
    by_key = {item.key: item for item in result.related}
    assert "BMS-452" in by_key
    assert by_key["BMS-452"].relation == "blocks"
    assert by_key["BMS-452"].discovered_via == "native"
    assert by_key["BMS-452"].web_url == "https://example.atlassian.net/browse/BMS-452"


async def test_jira_parent_is_included_as_a_relation() -> None:
    service, _ = _service()

    result = await service.list_related_items("jira", "BMS-451")

    parents = [item for item in result.related if item.relation == "parent"]
    assert [p.key for p in parents] == ["BMS-400"]


async def test_native_links_do_not_need_the_text_scan() -> None:
    service, handlers = _service()

    result = await service.list_related_items("jira", "BMS-451")

    assert all(item.discovered_via == "native" for item in result.related)
    # Only the issue fetch; no resolution lookups.
    assert len(handlers["jira"].requests) == 1


# -- jama --------------------------------------------------------------------


async def test_jama_upstream_and_downstream_become_related_items() -> None:
    service, _ = _service()

    result = await service.list_related_items("jama", "12345")

    assert result.system == "jama"
    assert result.item_title == "Battery shall report state of charge"
    directions = {item.relation for item in result.related}
    assert directions == {"upstream", "downstream"}
    assert all(item.key == "SRS-99" for item in result.related)


async def test_jama_rejects_a_document_key_with_a_clear_message() -> None:
    """Jama's get endpoint is by numeric id; a document key would 404 confusingly."""
    service, _ = _service()

    with pytest.raises(ValueError, match="numeric"):
        await service.list_related_items("jama", "SRS-42")


# -- confluence --------------------------------------------------------------


async def test_confluence_outbound_page_links_become_related_items() -> None:
    service, _ = _service(confluence_payload=CONFLUENCE_PAGE_WITH_LINKS)

    result = await service.list_related_items("confluence", "123456789")

    titles = [item.title for item in result.related]
    assert "Thermal Spec" in titles
    assert all(item.relation == "links-to" for item in result.related)


async def test_confluence_says_inbound_links_are_not_covered() -> None:
    """A partial answer has to announce itself."""
    service, _ = _service(confluence_payload=CONFLUENCE_PAGE_WITH_LINKS)

    result = await service.list_related_items("confluence", "123456789")

    assert any("inbound" in note for note in result.notes)


# -- genesys placeholder -----------------------------------------------------


async def test_genesys_reports_that_it_is_not_implemented() -> None:
    service, handlers = _service()

    result = await service.list_related_items("genesys", "e-1")

    assert result.related == []
    assert any("placeholder" in note for note in result.notes)
    # Must not have gone looking in the other systems.
    assert handlers["jira"].requests == []


async def test_an_unknown_system_is_rejected() -> None:
    service, _ = _service()

    with pytest.raises(ValueError, match="Unknown system"):
        await service.list_related_items("sharepoint", "1")


# -- text references (opt-in) ------------------------------------------------


async def test_text_references_are_off_by_default() -> None:
    """The Jama fixture's custom field says 'traced-to-JIRA-451' - ignore it unless asked."""
    service, handlers = _service()

    result = await service.list_related_items("jama", "12345")

    assert all(item.discovered_via == "native" for item in result.related)
    assert not any(r.url.path.startswith("/rest/api/3") for r in handlers["jira"].requests)


async def test_text_references_resolve_against_jira_when_enabled() -> None:
    service, _ = _service(
        confluence_payload=CONFLUENCE_PAGE_WITH_LINKS,
    )

    result = await service.list_related_items(
        "confluence", "123456789", include_text_references=True
    )

    text_hits = [item for item in result.related if item.discovered_via == "text"]
    assert [hit.key for hit in text_hits] == ["BMS-451"]
    assert text_hits[0].system == "jira"
    assert text_hits[0].title == "Cell balancing fails at high temperature"


async def test_a_key_that_matches_nothing_is_reported_as_unresolved() -> None:
    """Better to surface the reference as unresolved than to drop it silently."""
    service, _ = _service(
        jira_routes={"/issue/": (404, {})},
        jama_routes={
            "related": (200, {"data": []}),
            "/items/": (200, ITEM_PAYLOAD),
            "abstractitems": (200, {"data": []}),
        },
        confluence_payload=CONFLUENCE_PAGE_WITH_LINKS,
    )

    result = await service.list_related_items(
        "confluence", "123456789", include_text_references=True
    )

    unresolved = [item for item in result.related if item.system == "unresolved"]
    assert [item.key for item in unresolved] == ["BMS-451"]


async def test_a_text_key_falls_back_to_jama_when_jira_has_no_such_issue() -> None:
    jama_search_hit = {
        "data": [
            {"id": 555, "documentKey": "BMS-451", "project": 7, "fields": {"name": "From Jama"}}
        ]
    }
    service, _ = _service(
        jira_routes={"/issue/": (404, {})},
        jama_routes={
            "related": (200, {"data": []}),
            "/items/": (200, ITEM_PAYLOAD),
            "abstractitems": (200, jama_search_hit),
        },
        confluence_payload=CONFLUENCE_PAGE_WITH_LINKS,
    )

    result = await service.list_related_items(
        "confluence", "123456789", include_text_references=True
    )

    text_hits = [item for item in result.related if item.discovered_via == "text"]
    assert text_hits[0].system == "jama"
    assert text_hits[0].id == "555"


async def test_a_jama_search_hit_that_is_not_an_exact_key_match_is_not_used() -> None:
    """'contains' search is fuzzy; only an exact document-key match counts."""
    near_miss = {
        "data": [
            {"id": 1, "documentKey": "BMS-4510", "project": 7, "fields": {"name": "Different"}}
        ]
    }
    service, _ = _service(
        jira_routes={"/issue/": (404, {})},
        jama_routes={
            "related": (200, {"data": []}),
            "/items/": (200, ITEM_PAYLOAD),
            "abstractitems": (200, near_miss),
        },
        confluence_payload=CONFLUENCE_PAGE_WITH_LINKS,
    )

    result = await service.list_related_items(
        "confluence", "123456789", include_text_references=True
    )

    assert [i.system for i in result.related if i.discovered_via == "text"] == ["unresolved"]


async def test_text_lookups_are_capped_and_the_cap_is_announced() -> None:
    """An unbounded scan of a long page could fire hundreds of API calls."""
    many = " ".join(f"ABC-{n}" for n in range(1, MAX_TEXT_LOOKUPS + 6))
    page = {
        **PAGE_PAYLOAD,
        "body": {"storage": {"value": f"<p>{many}</p>", "representation": "storage"}},
    }
    service, handlers = _service(jira_routes={"/issue/": (404, {})}, confluence_payload=page)

    result = await service.list_related_items(
        "confluence", "123456789", include_text_references=True
    )

    assert len(handlers["jira"].requests) == MAX_TEXT_LOOKUPS
    assert any("only resolved the first" in note for note in result.notes)


async def test_a_key_already_linked_natively_is_not_duplicated_by_the_text_scan() -> None:
    service, _ = _service()

    result = await service.list_related_items("jira", "BMS-451", include_text_references=True)

    keys = [item.key for item in result.related]
    assert len(keys) == len(set(keys))


async def test_an_unconfigured_system_is_reported_not_treated_as_no_match() -> None:
    """A missing credential must not masquerade as 'nothing related'."""
    service, _ = _service(
        jira_routes={"/issue/": (404, {})},
        jama_configured=False,
        confluence_payload=CONFLUENCE_PAGE_WITH_LINKS,
    )

    result = await service.list_related_items(
        "confluence", "123456789", include_text_references=True
    )

    assert any("incomplete" in note for note in result.notes)
    assert any("JAMA_BASE_URL" in note for note in result.notes)
