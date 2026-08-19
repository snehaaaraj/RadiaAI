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


@pytest.mark.unit
def test_requirement_review_normalizes_fielded_document_text(client: TestClient) -> None:
    structured_text = """
    Project ID:
    [WR-ACR-732](https://radia.jamacloud.com/perspective.req?docId=731619&projectId=46)

    Title:
    Semi-Prepared Runway Operations (SPRO)

    Description:
    The WindRunner Aircraft shall be designed for takeoff, landing, and taxi operations on
    semi-prepared surfaces (e.g., compacted soil/gravel) with a California Bearing Ratio (CBR)
    of 9 or greater, without requiring ground support equipment for maneuvering.

    Requirement Volatility:
    Low
    """.strip()

    canonical_text = (
        "The WindRunner Aircraft shall be designed for takeoff, landing, and taxi operations on "
        "semi-prepared surfaces (e.g., compacted soil/gravel) with a California Bearing Ratio (CBR) "
        "of 9 or greater, without requiring ground support equipment for maneuvering."
    )

    structured = client.post(
        "/api/v1/review/requirement",
        json={
            "text": structured_text,
            "requirement_level": "system",
        },
    )
    canonical = client.post(
        "/api/v1/review/requirement",
        json={
            "text": canonical_text,
            "requirement_level": "system",
        },
    )

    assert structured.status_code == 200
    assert canonical.status_code == 200

    structured_data = structured.json()["data"]
    canonical_data = canonical.json()["data"]
    structured_data["review_id"] = "<ignored>"
    canonical_data["review_id"] = "<ignored>"
    assert structured_data == canonical_data
