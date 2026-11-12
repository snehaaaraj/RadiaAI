"""Unit tests for writing the reviewer-approved Description back to Jama."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import JamaSettings
from app.core.exceptions import JamaServiceError
from radia_ai.features.jama_requirement_reviewer.connectors.jama_client import (
    JamaApiCredentials,
    JamaClient,
    plain_text_to_jama_html,
)
from radia_ai.features.jama_requirement_reviewer.dependencies.container import get_jama_service
from radia_ai.features.jama_requirement_reviewer.services.jama_service import JamaService

ITEM_ID = 101
REVIEWED_MODIFIED_DATE = "2024-02-01T00:00:00.000+0000"
ORIGINAL_TEXT = "The subsystem should respond fast."


class _FakeJamaClient(JamaClient):
    """In-memory Jama item that records PATCH requests."""

    def __init__(self) -> None:
        super().__init__(
            JamaSettings(
                base_url="https://example.jamacloud.com",
            ),
            JamaApiCredentials("cid", "secret"),
        )
        self.patches: list[Any] = []
        self.field_definitions: list[dict[str, Any]] = []
        self.item: dict[str, Any] = {
            "id": ITEM_ID,
            "documentKey": "SYS-REQ-1",
            "project": 1,
            "itemType": 67,
            "modifiedDate": REVIEWED_MODIFIED_DATE,
            "fields": {
                "name": "Response requirement",
                "description": f"<p>{ORIGINAL_TEXT}</p>",
                "rationale": "<p>Keep it quick.</p>",
            },
        }

    def _request(  # type: ignore[override]
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | list[Any] | None = None,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        if path == "itemtypes/67" and method == "GET":
            return {"data": {"fields": self.field_definitions}}
        assert path == f"items/{ITEM_ID}", path
        if method == "GET":
            return {"data": self.item}
        if method == "PATCH":
            self.patches.append(json)
            target = {
                key: value
                for key, value in self.item["fields"].items()
                if value is not None and value is not False
            }
            supplied = set()
            for op in json or []:
                field_name = (
                    op["path"].removeprefix("/fields/").replace("~1", "/").replace("~0", "~")
                )
                if op["op"] == "replace" and field_name not in target:
                    raise JamaServiceError("no such path in target JSON document", operation=path)
                target[field_name] = op["value"]
                supplied.add(field_name)
            for field in self.field_definitions:
                name = field.get("name")
                if (
                    field.get("required") is True
                    and field.get("readOnly") is not True
                    and name in self.item["fields"]
                    and self.item["fields"][name] is not None
                    and name not in supplied
                ):
                    raise JamaServiceError(f"Mandatory field omitted: {name}", operation=path)
            self.item["fields"].update(target)
            self.item["modifiedDate"] = f"2024-03-0{len(self.patches)}T00:00:00.000+0000"
            return {}
        raise AssertionError(f"Unexpected method {method}")


@pytest.fixture
def fake_jama(test_app) -> Iterator[_FakeJamaClient]:
    client = _FakeJamaClient()
    service = JamaService(client)
    test_app.dependency_overrides[get_jama_service] = lambda: service
    yield client
    test_app.dependency_overrides.pop(get_jama_service, None)


def _run_jama_review(client: TestClient, **overrides: Any) -> dict[str, Any]:
    body = {
        "requirement_id": "SYS-REQ-1",
        "text": ORIGINAL_TEXT,
        "jama_item_id": ITEM_ID,
        "jama_modified_date": REVIEWED_MODIFIED_DATE,
        **overrides,
    }
    response = client.post("/api/v1/review/requirement", json=body)
    assert response.status_code == 200
    return response.json()["data"]


def _decide(client: TestClient, review_id: str, **payload: Any) -> None:
    response = client.post(f"/api/v1/review/history/{review_id}/decision", json=payload)
    assert response.status_code == 200, response.json()


def _write(client: TestClient, review_id: str) -> Any:
    return client.post(f"/api/v1/review/history/{review_id}/jama-write")


@pytest.mark.unit
def test_plain_text_to_jama_html_escapes_and_keeps_line_structure() -> None:
    html = plain_text_to_jama_html("The system shall stop < 50 m & hold.\nLine two\n\nPara two")
    assert html == "<p>The system shall stop &lt; 50 m &amp; hold.<br />Line two</p><p>Para two</p>"


@pytest.mark.unit
@pytest.mark.parametrize("flag", [False, True])
@pytest.mark.parametrize("release", [115, 0])
def test_jrr_preserves_required_values_on_sparse_patch_target(
    client: TestClient, fake_jama: _FakeJamaClient, flag: bool, release: int
) -> None:
    values = {
        "release": release,
        "derived_requirement$67": flag,
        "safety_requirement$67": flag,
        "cybersecurity_requirement$67": flag,
        "verification_method$67": [673, 674],
        "empty_selection$67": [],
        "empty_text$67": "",
        "required_richtext$67": "<p>Existing &amp; unchanged</p>",
        "escaped/~field$67": 0,
    }
    fake_jama.item["fields"].update(values)
    fake_jama.field_definitions = [
        {"name": name, "required": True, "readOnly": False} for name in values
    ] + [
        {"name": "description", "required": True},
        {"name": "missing", "required": True},
        {"name": "null_field", "required": True},
        {"name": "rationale", "required": False},
        {"name": "locked", "required": True, "readOnly": True},
    ]
    fake_jama.item["fields"]["null_field"] = None
    fake_jama.item["fields"]["locked"] = "read-only"
    review = _run_jama_review(client)
    _decide(client, review["review_id"], decision="ready_to_replace")
    response = _write(client, review["review_id"])
    assert response.status_code == 200, response.json()
    patches = fake_jama.patches[0]
    recommended = review["final_recommendation"]["recommended_description"]
    assert patches == [
        {
            "op": "add",
            "path": "/fields/description",
            "value": plain_text_to_jama_html(recommended),
        },
        *[
            {
                "op": "add",
                "path": "/fields/" + name.replace("~", "~0").replace("/", "~1"),
                "value": value,
            }
            for name, value in values.items()
        ],
    ]
    assert {name: fake_jama.item["fields"][name] for name in values} == values
    assert "missing" not in fake_jama.item["fields"]
    assert fake_jama.item["fields"]["null_field"] is None


@pytest.mark.unit
@pytest.mark.parametrize("old_value", [None, False])
def test_jrr_description_can_be_set_when_missing_from_patch_target(old_value: Any) -> None:
    jama = _FakeJamaClient()
    jama.item["fields"]["description"] = old_value
    result = jama.update_description(ITEM_ID, "Updated")
    assert result.description == "Updated"
    assert jama.patches == [
        [
            {
                "op": "add",
                "path": "/fields/description",
                "value": "<p>Updated</p>",
            }
        ]
    ]


@pytest.mark.unit
@pytest.mark.parametrize("definition", [None, {"name": "", "required": True}])
def test_jrr_invalid_required_metadata_fails_before_patch(definition: Any) -> None:
    jama = _FakeJamaClient()
    jama.field_definitions = [definition]
    with pytest.raises(JamaServiceError, match="invalid"):
        jama.update_description(ITEM_ID, "Updated")
    assert jama.patches == []


@pytest.mark.unit
def test_ready_to_replace_writes_the_final_recommendation_exactly(
    client: TestClient, fake_jama: _FakeJamaClient
) -> None:
    review = _run_jama_review(client)
    recommended = review["final_recommendation"]["recommended_description"]
    assert recommended
    _decide(client, review["review_id"], decision="ready_to_replace")

    response = _write(client, review["review_id"])

    assert response.status_code == 200, response.json()
    # Only the Description field is patched, with exactly the recommended text.
    assert fake_jama.patches == [
        [
            {
                "op": "add",
                "path": "/fields/description",
                "value": plain_text_to_jama_html(recommended),
            }
        ]
    ]
    assert fake_jama.item["fields"]["rationale"] == "<p>Keep it quick.</p>"
    write = response.json()["data"]["jama_write"]
    assert write["item_id"] == ITEM_ID
    assert write["document_key"] == "SYS-REQ-1"
    assert write["decision"] == "ready_to_replace"
    assert write["description"] == recommended.strip()


@pytest.mark.unit
def test_accept_but_modify_writes_the_reviewer_text_exactly(
    client: TestClient, fake_jama: _FakeJamaClient
) -> None:
    review = _run_jama_review(client)
    modified = "The subsystem shall respond within 200 ms."
    _decide(
        client,
        review["review_id"],
        decision="accepted_with_modifications",
        modified_description=modified,
    )

    response = _write(client, review["review_id"])

    assert response.status_code == 200, response.json()
    assert fake_jama.patches[0][0]["value"] == plain_text_to_jama_html(modified)
    write = response.json()["data"]["jama_write"]
    assert write["decision"] == "accepted_with_modifications"
    assert write["description"] == modified


@pytest.mark.unit
def test_rejected_recommendation_is_never_written(
    client: TestClient, fake_jama: _FakeJamaClient
) -> None:
    review = _run_jama_review(client)
    _decide(client, review["review_id"], decision="rejected", reason="Not accurate.")

    response = _write(client, review["review_id"])

    assert response.status_code == 422
    assert fake_jama.patches == []


@pytest.mark.unit
def test_write_requires_a_saved_decision(client: TestClient, fake_jama: _FakeJamaClient) -> None:
    review = _run_jama_review(client)

    response = _write(client, review["review_id"])

    assert response.status_code == 422
    assert "decision" in response.json()["error"]["message"].lower()
    assert fake_jama.patches == []


@pytest.mark.unit
def test_write_requires_a_review_pulled_from_jama(
    client: TestClient, fake_jama: _FakeJamaClient
) -> None:
    review = _run_jama_review(client, jama_item_id=None, jama_modified_date=None)
    _decide(client, review["review_id"], decision="ready_to_replace")

    response = _write(client, review["review_id"])

    assert response.status_code == 422
    assert "jama" in response.json()["error"]["message"].lower()
    assert fake_jama.patches == []


@pytest.mark.unit
def test_write_refuses_to_overwrite_a_jama_change_made_after_the_review(
    client: TestClient, fake_jama: _FakeJamaClient
) -> None:
    review = _run_jama_review(client)
    _decide(client, review["review_id"], decision="ready_to_replace")
    fake_jama.item["modifiedDate"] = "2024-02-15T00:00:00.000+0000"

    response = _write(client, review["review_id"])

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "JAMA_WRITE_CONFLICT"
    assert fake_jama.patches == []


@pytest.mark.unit
def test_changed_decision_can_be_written_again_after_a_previous_write(
    client: TestClient, fake_jama: _FakeJamaClient
) -> None:
    review = _run_jama_review(client)
    _decide(client, review["review_id"], decision="ready_to_replace")
    assert _write(client, review["review_id"]).status_code == 200

    modified = "The subsystem shall respond within 100 ms."
    _decide(
        client,
        review["review_id"],
        decision="accepted_with_modifications",
        modified_description=modified,
    )
    response = _write(client, review["review_id"])

    assert response.status_code == 200, response.json()
    assert len(fake_jama.patches) == 2
    assert fake_jama.patches[1][0]["value"] == plain_text_to_jama_html(modified)
