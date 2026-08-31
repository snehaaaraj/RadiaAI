"""Unit tests for standards and review history endpoints."""

import pytest
from fastapi.testclient import TestClient

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    ConsolidatedReviewResult,
    ReviewCompletion,
)


@pytest.mark.unit
def test_get_standards_returns_references(client: TestClient) -> None:
    response = client.get("/api/v1/standards")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    standards = body["data"]["standards"]
    assert len(standards) >= 1
    assert any(item["key"] == "incose" for item in standards)


@pytest.mark.unit
def test_review_history_and_disposition_flow(client: TestClient) -> None:
    review_response = client.post(
        "/api/v1/review/requirement",
        json={"requirement_id": "REQ-HIST-1", "text": "The subsystem should respond fast."},
    )
    assert review_response.status_code == 200

    history_response = client.get("/api/v1/review/history")
    assert history_response.status_code == 200
    history_body = history_response.json()
    assert history_body["success"] is True
    entries = history_body["data"]["entries"]
    assert len(entries) >= 1

    latest_entry = entries[0]
    review_id = latest_entry["review_id"]
    assert latest_entry["workflow"] == "requirement"
    assert len(latest_entry["findings"]) >= 1

    disposition_response = client.post(
        f"/api/v1/review/history/{review_id}/disposition",
        json={
            "finding_index": 0,
            "disposition": "Accepted",
            "reviewer_comment": "Acknowledged and accepted for update.",
            "reviewer_id": "engineer@example.com",
        },
    )
    assert disposition_response.status_code == 200
    disposition_body = disposition_response.json()
    assert disposition_body["success"] is True
    dispositions = disposition_body["data"]["dispositions"]
    assert len(dispositions) == 1
    assert dispositions[0]["disposition"] == "Accepted"


@pytest.mark.unit
def test_review_history_rejects_out_of_range_finding_index(
    client: TestClient, review_engine
) -> None:
    """A disposition pointing past the stored findings is rejected, not recorded."""
    review_engine.install(
        ConsolidatedReviewResult(findings=[], completion=ReviewCompletion.complete())
    )

    review_response = client.post(
        "/api/v1/review/requirement",
        json={"requirement_id": "REQ-HIST-EMPTY", "text": "The subsystem shall respond."},
    )
    assert review_response.status_code == 200
    review_id = review_response.json()["data"]["review_id"]

    disposition_response = client.post(
        f"/api/v1/review/history/{review_id}/disposition",
        json={"finding_index": 0, "disposition": "Accepted"},
    )

    assert disposition_response.status_code == 422
    disposition_body = disposition_response.json()
    assert disposition_body["success"] is False
    assert disposition_body["error"]["message"] == "Finding index is out of range for this review."
