"""Unit tests for individual requirement review endpoint."""

import pytest
from fastapi.testclient import TestClient

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    RequirementReviewInput,
)
from radia_ai.features.jama_requirement_reviewer.utils.requirement_normalization import (
    normalize_requirement_review_input,
)


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
    """Fielded Jama document text should be accepted and produce a valid review result."""
    structured_text = """
    Project ID:
    [WR-ACR-732](https://radia.jamacloud.com/perspective.req?docId=731619&projectId=46)

    Title:
    Semi-Prepared Runway Operations (SPRO)

    Description:
    The WindRunner Aircraft shall be designed for takeoff, landing, and taxi operations on
    semi-prepared surfaces (e.g., compacted soil/gravel) with a California Bearing Ratio (CBR)
    of 9 or greater, without requiring ground support equipment for maneuvering.

    Rationale:
    Ensures mission compatibility with SPRO sites

    Requirement Volatility:
    Low
    """.strip()

    response = client.post(
        "/api/v1/review/requirement",
        json={
            "text": structured_text,
            "requirement_level": "system",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "overall" in data
    assert "category_results" in data
    assert "findings" in data


@pytest.mark.unit
def test_requirement_review_normalization_preserves_wrapped_field_lines() -> None:
    raw_text = """
    Title: Lubrication, Movable Pin Arrangements

    Description: Movable Pin Arrangements Unless permanently sealed by design, all movable pin
    arrangements on the aircraft shall have a means to lubricate the joints with grease fittings
    or other materials that prevent corrosion or damage of the movable pin arrangement.

    Rationale: Prevention against corrosion. See WR-ACR-241 for conditions of
    Permanent Sealing & Servicing.
    """.strip()

    normalized = normalize_requirement_review_input(
        RequirementReviewInput(text=raw_text, requirement_level="aircraft")
    )

    assert normalized.text == (
        "Title: Lubrication, Movable Pin Arrangements\n\n"
        "Description: Movable Pin Arrangements Unless permanently sealed by design, all movable pin "
        "arrangements on the aircraft shall have a means to lubricate the joints with grease fittings "
        "or other materials that prevent corrosion or damage of the movable pin arrangement.\n\n"
        "Rationale: Prevention against corrosion. See WR-ACR-241 for conditions of Permanent Sealing & Servicing."
    )


@pytest.mark.unit
def test_requirement_review_normalization_drops_trailing_metadata_on_rationale_line() -> None:
    raw_text = """
    Title: Lubrication, Movable Pin Arrangements

    Description: Movable Pin Arrangements Unless permanently sealed by design, all movable pin arrangements
    on the aircraft shall have a means to lubricate the joints with grease fittings or other materials that
    prevent corrosion or damage of the movable pin arrangement. Note: design solution will be system and case specific.

    Rationale: Prevention against corrosion. See WR-ACR-241 for conditions of Permanent Sealing & Servicing.
    Requirement Volatility Low Derived Requirement No Safety Requirement No Security Effectiveness Requirement No
    Validation Method Engineering Review,Traceability Verification Method Undetermined,Inspection,Review
    """.strip()

    normalized = normalize_requirement_review_input(
        RequirementReviewInput(text=raw_text, requirement_level="aircraft")
    )

    assert normalized.text == (
        "Title: Lubrication, Movable Pin Arrangements\n\n"
        "Description: Movable Pin Arrangements Unless permanently sealed by design, all movable pin arrangements "
        "on the aircraft shall have a means to lubricate the joints with grease fittings or other materials that "
        "prevent corrosion or damage of the movable pin arrangement. Note: design solution will be system and case specific.\n\n"
        "Rationale: Prevention against corrosion. See WR-ACR-241 for conditions of Permanent Sealing & Servicing."
    )


@pytest.mark.unit
def test_requirement_review_normalization_drops_heading_line_from_description() -> None:
    raw_text = """
    1 WR-ACR-732 Semi-Prepared Runway Operations (SPRO)
    The WindRunner Aircraft shall be designed for takeoff, landing, and taxi operations on
    semi-prepared surfaces (e.g., compacted soil/gravel) with a California Bearing Ratio (CBR)
    of 9 or greater, without requiring ground support equipment for maneuvering.

    Project ID WR-ACR-732
    Title Semi-Prepared Runway Operations (SPRO)
    Rationale Ensures mission compatibility with SPRO sites
    Requirement Volatility Low
    """.strip()

    normalized = normalize_requirement_review_input(
        RequirementReviewInput(text=raw_text, requirement_level="aircraft")
    )

    assert normalized.text == (
        "Title: Semi-Prepared Runway Operations (SPRO)\n\n"
        "Description: The WindRunner Aircraft shall be designed for takeoff, landing, and taxi operations on "
        "semi-prepared surfaces (e.g., compacted soil/gravel) with a California Bearing Ratio (CBR) of 9 or greater, "
        "without requiring ground support equipment for maneuvering.\n\n"
        "Rationale: Ensures mission compatibility with SPRO sites"
    )
