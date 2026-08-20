"""
Unit tests for health check endpoint.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.unit
def test_health_response_structure(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    body = response.json()

    assert body["success"] is True
    assert "data" in body
    assert body["data"]["status"] in ("ok", "degraded", "down")
    assert "version" in body["data"]
    assert "environment" in body["data"]
    assert "dependencies" in body["data"]


@pytest.mark.unit
def test_health_includes_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers


@pytest.mark.unit
def test_health_echoes_provided_request_id(client: TestClient) -> None:
    custom_id = "test-request-id-12345"
    response = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert response.headers["X-Request-ID"] == custom_id
