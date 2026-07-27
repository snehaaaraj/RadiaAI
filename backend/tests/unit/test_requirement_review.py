"""Unit tests for individual requirement review endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_requirement_review_returns_200(client: TestClient) -> None:
    response = client.post(
        "/api/v1/review/requirement",
        json={"text": "The subsystem shall provide data within 100 ms under nominal load."},
    )
    assert response.status_code == 200


@pytest.mark.unit
def test_requirement_review_returns_structured_findings(client: TestClient) -> None:
    response = client.post(
        "/api/v1/review/requirement",
        json={
            "text": "The subsystem should respond fast and user-friendly.",
            "requirement_level": "system",
        },
    )
    body = response.json()
    assert body["success"] is True

    data = body["data"]
    assert "overall" in data
    assert "category_results" in data
    assert "findings" in data
    assert "determinism" in data
    assert data["overall"] in ("Acceptable", "Revision Recommended", "Unacceptable")
    assert any(result["category"] == "language" for result in data["category_results"])
    assert any(finding["pass_fail"] in ("Pass", "Fail") for finding in data["findings"])


@pytest.mark.unit
def test_requirement_review_is_deterministic_for_identical_input(client: TestClient) -> None:
    payload = {
        "requirement_id": "REQ-001",
        "text": "The component should provide fast response.",
        "requirement_level": "component",
    }
    first = client.post("/api/v1/review/requirement", json=payload)
    second = client.post("/api/v1/review/requirement", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    first_data["review_id"] = "<ignored>"
    second_data["review_id"] = "<ignored>"
    assert first_data == second_data
