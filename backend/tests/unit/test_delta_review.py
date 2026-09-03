"""Unit tests for deterministic delta review endpoint."""

import pytest
from fastapi.testclient import TestClient


def _build_delta_payload() -> dict:
    return {
        "specification_id": "SPEC-DELTA-1",
        "baseline_requirements": [
            {
                "requirement_id": "REQ-001",
                "text": "The system shall enable diagnostics within 2 seconds.",
                "requirement_level": "system",
                "metadata": {"parent_id": "P-100", "verification_method": "test"},
            },
            {
                "requirement_id": "REQ-002",
                "text": "The system shall provide telemetry every 1 second.",
                "requirement_level": "system",
                "metadata": {"parent_id": "P-100", "verification_method": "analysis"},
            },
        ],
        "updated_requirements": [
            {
                "requirement_id": "REQ-001",
                "text": "The system shall enable diagnostics within 1 second.",
                "requirement_level": "system",
                "metadata": {"parent_id": "P-100", "verification_method": "test"},
            },
            {
                "requirement_id": "REQ-003",
                "text": "The system shall provide built-in test under nominal conditions.",
                "requirement_level": "system",
                "metadata": {"parent_id": "P-110", "verification_method": "inspection"},
            },
        ],
    }


@pytest.mark.unit
def test_delta_review_returns_200(client: TestClient) -> None:
    response = client.post("/api/v1/review/delta", json=_build_delta_payload())
    assert response.status_code == 200


@pytest.mark.unit
def test_delta_review_returns_expected_change_summary(client: TestClient) -> None:
    response = client.post("/api/v1/review/delta", json=_build_delta_payload())
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["change_summary"]["new_requirement_ids"] == ["REQ-003"]
    assert data["change_summary"]["modified_requirement_ids"] == ["REQ-001"]
    assert data["change_summary"]["deleted_requirement_ids"] == ["REQ-002"]
    reviewed_ids = [item["requirement_id"] for item in data["reviewed_requirements"]]
    assert reviewed_ids == ["REQ-001", "REQ-003"]


@pytest.mark.unit
def test_delta_review_is_deterministic(client: TestClient) -> None:
    payload = _build_delta_payload()
    first = client.post("/api/v1/review/delta", json=payload)
    second = client.post("/api/v1/review/delta", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    first_data["review_id"] = "<ignored>"
    second_data["review_id"] = "<ignored>"
    assert first_data == second_data
