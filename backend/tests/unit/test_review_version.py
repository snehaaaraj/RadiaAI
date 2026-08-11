"""Unit tests for review version endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_review_version_returns_200(client: TestClient) -> None:
    response = client.get("/api/v1/review/version")
    assert response.status_code == 200


@pytest.mark.unit
def test_review_version_response_structure(client: TestClient) -> None:
    response = client.get("/api/v1/review/version")
    body = response.json()

    assert body["success"] is True
    assert "data" in body
    data = body["data"]
    assert data["product"] == "Radia AI Requirements Engineering Assistant"
    assert data["workflow_default"] == "requirement"
    assert "determinism" in data
    assert "reviewers" in data
    assert len(data["reviewers"]) >= 1

    determinism = data["determinism"]
    assert determinism["reviewer_bundle_version"] == "1.0.0"
    assert determinism["config_snapshot"]["temperature"] == 0.0
    assert isinstance(determinism["config_hash"], str)
    assert len(determinism["config_hash"]) == 64

