"""Unit tests for the Jama Connect integration endpoints."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import JamaSettings
from radia_ai.features.jama_requirement_reviewer.connectors.jama_client import (
    JamaClient,
    _strip_html,
)
from radia_ai.features.jama_requirement_reviewer.services.jama_service import JamaService


def _configured_settings() -> JamaSettings:
    return JamaSettings(
        base_url="https://example.jamacloud.com",
        auth_type="basic",
        username="api-id",
        password="api-key",
    )


class _StubJamaClient(JamaClient):
    """JamaClient whose HTTP layer is replaced with canned Jama payloads."""

    def __init__(self, responses: dict[str, Any]) -> None:
        super().__init__(_configured_settings())
        self._responses = responses

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:  # type: ignore[override]
        # Match on the leading path segment so items/{id} resolves too.
        if path in self._responses:
            return self._responses[path]
        for key, value in self._responses.items():
            if path.startswith(key):
                return value
        raise AssertionError(f"Unexpected Jama path requested: {path}")


@pytest.fixture
def jama_client(test_app) -> Iterator[None]:
    """Install a stub Jama service on the app and remove it afterwards."""
    responses = {
        "projects": {
            "data": [
                {"id": 1, "projectKey": "SYS", "fields": {"name": "Aircraft Systems"}},
                {"id": 2, "projectKey": "FLD", "isFolder": True, "fields": {"name": "Folder"}},
            ]
        },
        "abstractitems": {
            "data": [
                {
                    "id": 101,
                    "documentKey": "SYS-REQ-1",
                    "globalId": "GID-101",
                    "itemType": 33,
                    "project": 1,
                    "fields": {"name": "Braking response requirement"},
                }
            ],
            "meta": {"pageInfo": {"startIndex": 0, "resultCount": 1, "totalResults": 1}},
        },
        "items/101": {
            "data": {
                "id": 101,
                "documentKey": "SYS-REQ-1",
                "globalId": "GID-101",
                "itemType": 33,
                "project": 1,
                "createdDate": "2024-01-01T00:00:00.000+0000",
                "modifiedDate": "2024-02-01T00:00:00.000+0000",
                "fields": {
                    "name": "Braking response requirement",
                    "description": "<p>The system <b>shall</b> stop within 50&nbsp;m.</p>",
                    "status": "Approved",
                },
            }
        },
    }
    test_app.state.jama_service = JamaService(_StubJamaClient(responses))
    yield
    if hasattr(test_app.state, "jama_service"):
        delattr(test_app.state, "jama_service")


@pytest.mark.unit
def test_strip_html_normalizes_rich_text() -> None:
    result = _strip_html("<p>The system <b>shall</b> stop within 50&nbsp;m.</p>")
    assert result == "The system shall stop within 50\xa0m."


@pytest.mark.unit
def test_projects_endpoint_returns_projects_excluding_folders(
    client: TestClient, jama_client: None
) -> None:
    response = client.get("/api/v1/jama/projects")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    projects = body["data"]["projects"]
    assert len(projects) == 1
    assert projects[0]["id"] == 1
    assert projects[0]["name"] == "Aircraft Systems"


@pytest.mark.unit
def test_search_requirements_endpoint(client: TestClient, jama_client: None) -> None:
    response = client.get("/api/v1/jama/requirements", params={"project_id": 1, "contains": "brak"})
    assert response.status_code == 200
    body = response.json()
    results = body["data"]["results"]
    assert body["data"]["total"] == 1
    assert results[0]["document_key"] == "SYS-REQ-1"


@pytest.mark.unit
def test_get_requirement_endpoint_normalizes_description(
    client: TestClient, jama_client: None
) -> None:
    response = client.get("/api/v1/jama/requirements/101")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == 101
    assert data["document_key"] == "SYS-REQ-1"
    assert data["status"] == "Approved"
    assert "shall stop within" in data["description"]
    assert data["web_url"].endswith("/items/101?projectId=1")


@pytest.mark.unit
def test_endpoints_report_not_configured(client: TestClient) -> None:
    # No stub installed and test settings leave Jama unconfigured.
    response = client.get("/api/v1/jama/projects")
    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "JAMA_NOT_CONFIGURED"
