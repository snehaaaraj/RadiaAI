"""Unit tests for requirement-set review endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_requirement_set_review_returns_200(client: TestClient) -> None:
    response = client.post(
        "/api/v1/review/requirement-set",
        json={
            "specification_id": "SPEC-001",
            "requirements": [
                {
                    "requirement_id": "REQ-001",
                    "text": (
                        "The system shall provide altitude data within 100 ms "
                        "under nominal conditions."
                    ),
                    "requirement_level": "system",
                    "metadata": {"parent_id": "PR-1", "verification_method": "test"},
                }
            ],
        },
    )
    assert response.status_code == 200


@pytest.mark.unit
def test_requirement_set_review_returns_structured_results(client: TestClient) -> None:
    payload = {
        "specification_id": "SPEC-002",
        "requirements": [
            {
                "requirement_id": "REQ-001",
                "text": "The subsystem shall enable diagnostics.",
                "requirement_level": "subsystem",
                "metadata": {"parent_id": "", "verification_method": ""},
            },
            {
                "requirement_id": "REQ-002",
                "text": "The subsystem shall disable diagnostics.",
                "requirement_level": "subsystem",
                "metadata": {"parent_id": "", "verification_method": ""},
            },
            {
                "requirement_id": "REQ-003",
                "text": "The subsystem shall enable diagnostics.",
                "requirement_level": "subsystem",
                "metadata": {"parent_id": "", "verification_method": ""},
            },
        ],
    }

    response = client.post("/api/v1/review/requirement-set", json=payload)
    body = response.json()
    assert body["success"] is True
    assert "data" in body
    data = body["data"]
    assert data["overall"] in ("Acceptable", "Revision Recommended", "Unacceptable")
    assert data["requirement_count"] == 3
    assert len(data["category_results"]) >= 1
    assert len(data["findings"]) >= 1


@pytest.mark.unit
def test_requirement_set_review_is_deterministic_for_identical_input(client: TestClient) -> None:
    payload = {
        "specification_id": "SPEC-DET",
        "requirements": [
            {
                "requirement_id": "REQ-A",
                "text": "The aircraft shall include a backup power unit.",
                "requirement_level": "aircraft",
                "metadata": {"parent_id": "TOP-1", "verification_method": "inspection"},
            },
            {
                "requirement_id": "REQ-B",
                "text": "The aircraft shall include a backup power unit.",
                "requirement_level": "aircraft",
                "metadata": {"parent_id": "TOP-1", "verification_method": "inspection"},
            },
        ],
    }
    first = client.post("/api/v1/review/requirement-set", json=payload)
    second = client.post("/api/v1/review/requirement-set", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"] == second.json()["data"]
