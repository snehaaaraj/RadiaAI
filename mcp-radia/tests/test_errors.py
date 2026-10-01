"""Tests for connector error translation and remote-message extraction.

The wording an API returns is often the only actionable part of a failure -
Jira answers a bare ORDER BY with 400 and the words "Unbounded JQL queries are
not allowed here". These tests pin that wording surviving into the string the
model is shown.
"""

import pytest

from mcp_radia.connectors.errors import (
    ConnectorError,
    ConnectorServiceError,
    ItemNotFoundError,
    extract_remote_message,
)

pytestmark = pytest.mark.unit


# -- extraction --------------------------------------------------------------


def test_extracts_atlassian_error_messages() -> None:
    body = '{"errorMessages":["Unbounded JQL queries are not allowed here."],"errors":{}}'

    assert extract_remote_message(body) == "Unbounded JQL queries are not allowed here."


def test_extracts_atlassian_field_errors() -> None:
    body = '{"errorMessages":[],"errors":{"jql":"Field \'nope\' does not exist."}}'

    assert extract_remote_message(body) == "jql: Field 'nope' does not exist."


def test_extracts_confluence_error_object_list() -> None:
    """Confluence v2 nests wording in a list of objects, not a flat string."""
    body = (
        '{"errors":[{"status":404,"code":"NOT_FOUND",'
        '"title":"Cannot find a page with id [123]","detail":null}]}'
    )

    assert extract_remote_message(body) == "Cannot find a page with id [123]"


def test_extracts_jama_meta_message() -> None:
    body = '{"meta":{"status":"Not Found","message":"Item with ID \\"9\\" does not exist"}}'

    assert extract_remote_message(body) == 'Item with ID "9" does not exist'


def test_extracts_oauth_error_description() -> None:
    body = '{"error":"invalid_client","error_description":"Client authentication failed"}'
    result = extract_remote_message(body)

    assert result is not None
    assert "Client authentication failed" in result


def test_deduplicates_repeated_wording() -> None:
    """APIs often repeat one message in two fields; showing it twice is noise."""
    body = '{"message":"Nope","errorMessages":["Nope"]}'

    assert extract_remote_message(body) == "Nope"


@pytest.mark.parametrize("body", ["", "   ", "{}", '{"meta":{}}', '{"unrelated":123}'])
def test_returns_none_when_there_is_no_message(body: str) -> None:
    assert extract_remote_message(body) is None


def test_ignores_html_error_pages() -> None:
    """A gateway's HTML page is noise, not a remediation hint."""
    assert extract_remote_message("<html><body>502 Bad Gateway</body></html>") is None


def test_passes_through_short_plain_text() -> None:
    assert extract_remote_message("Service temporarily unavailable") == (
        "Service temporarily unavailable"
    )


def test_long_messages_are_truncated() -> None:
    """A huge body must not flood the model's context."""
    body = '{"message":"' + "x" * 5000 + '"}'
    result = extract_remote_message(body)

    assert result is not None
    assert len(result) <= 400
    assert result.endswith("…")


def test_non_json_long_text_is_dropped() -> None:
    assert extract_remote_message("y" * 5000) is None


# -- surfacing in the error string -------------------------------------------


def test_remote_message_appears_in_the_error_string() -> None:
    exc = ConnectorServiceError(
        "The Jira API returned an error response.",
        system="jira",
        operation="rest/api/3/search/jql",
        status_code=400,
        remote_message="Unbounded JQL queries are not allowed here.",
    )
    rendered = str(exc)

    assert "status=400" in rendered
    assert 'jira said: "Unbounded JQL queries are not allowed here."' in rendered


def test_error_string_is_unchanged_when_there_is_no_remote_message() -> None:
    exc = ItemNotFoundError(
        "The requested Jama resource was not found.",
        system="jama",
        operation="items/9",
        status_code=404,
    )

    assert (
        str(exc) == "[jama] The requested Jama resource was not found. operation=items/9 status=404"
    )


def test_remote_message_is_exposed_as_a_property() -> None:
    exc = ConnectorError("boom", system="jama", remote_message="because reasons")

    assert exc.remote_message == "because reasons"


def test_remote_message_property_is_none_when_absent() -> None:
    assert ConnectorError("boom", system="jama").remote_message is None


def test_detail_passed_by_caller_is_preserved_alongside_remote_message() -> None:
    exc = ConnectorError(
        "boom",
        system="jama",
        detail={"item_id": 42},
        remote_message="nope",
    )

    assert exc.detail["item_id"] == 42
    assert exc.remote_message == "nope"


def test_caller_detail_is_not_mutated() -> None:
    """The connector's own dict must not gain keys as a side effect."""
    original: dict[str, object] = {"item_id": 42}
    ConnectorError("boom", system="jama", detail=original, remote_message="nope")

    assert original == {"item_id": 42}
