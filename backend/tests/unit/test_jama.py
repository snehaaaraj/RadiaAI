"""Unit tests for the Jama Connect integration endpoints."""

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import JamaSettings
from app.core.exceptions import JamaServiceError
from radia_ai.features.jama_requirement_reviewer.connectors import jama_client as jama_client_module
from radia_ai.features.jama_requirement_reviewer.connectors.jama_client import (
    JamaApiCredentials,
    JamaClient,
    _jama_error_message,
    _strip_html,
    plain_text_to_jama_html,
)
from radia_ai.features.jama_requirement_reviewer.dependencies.container import get_jama_service
from radia_ai.features.jama_requirement_reviewer.services.jama_service import JamaService


def _configured_settings() -> JamaSettings:
    return JamaSettings(
        base_url="https://example.jamacloud.com",
    )


class _StubJamaClient(JamaClient):
    """JamaClient whose HTTP layer is replaced with canned Jama payloads."""

    def __init__(self, responses: dict[str, Any]) -> None:
        super().__init__(_configured_settings(), JamaApiCredentials("cid", "secret"))
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
                    "rationale": "<p>To ensure adequate stopping distance.</p>",
                    "status": "Approved",
                },
            }
        },
    }
    stub_service = JamaService(_StubJamaClient(responses))
    test_app.dependency_overrides[get_jama_service] = lambda: stub_service
    yield
    test_app.dependency_overrides.pop(get_jama_service, None)


@pytest.mark.unit
def test_strip_html_normalizes_rich_text() -> None:
    result = _strip_html("<p>The system <b>shall</b> stop within 50&nbsp;m.</p>")
    assert result == "The system shall stop within 50\xa0m."


@pytest.mark.unit
@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"meta": {"message": " Invalid\n patch\tpath. "}}, "Invalid patch path."),
        ({"meta": {"message": "x" * 1001}}, "x" * 1000 + "..."),
        ({"meta": {"message": " "}}, None),
        ({"meta": {"message": ["Private data"]}}, None),
        ({"meta": {"message": None}}, None),
        ({"meta": "Private data"}, None),
        ({"meta": None}, None),
        ({"data": {"description": "Private data"}}, None),
        ([], None),
        (None, None),
    ],
)
def test_jama_error_message_only_extracts_bounded_meta_message(
    body: Any, expected: str | None
) -> None:
    assert _jama_error_message(httpx.Response(400, json=body)) == expected


@pytest.mark.unit
@pytest.mark.parametrize("body", [b"", b"<html>Gateway error</html>", b"{invalid", b"\xff"])
def test_jama_error_message_ignores_non_json_bodies(body: bytes) -> None:
    assert _jama_error_message(httpx.Response(400, content=body)) is None


@pytest.mark.unit
@pytest.mark.parametrize("patch_status", [200, 400, 415, 500])
def test_update_description_http_contract(
    monkeypatch: pytest.MonkeyPatch, patch_status: int
) -> None:
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/rest/v1/itemtypes/67":
            return httpx.Response(200, json={"data": {"fields": []}})
        if request.method == "PATCH":
            if request.headers["content-type"] != "application/json":
                return httpx.Response(415, text="Unsupported Media Type")
            if patch_status == 200:
                return httpx.Response(200, json={})
            return httpx.Response(
                patch_status,
                json={
                    "meta": {"message": "The requested field cannot be updated."},
                    "data": {"description": "Private upstream response"},
                },
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "id": 101,
                    "project": 1,
                    "itemType": 67,
                    "fields": {"name": "Requirement", "description": "<p>Updated</p>"},
                }
            },
        )

    transport = httpx.MockTransport(handle_request)
    original_client = httpx.Client

    class MockHttpClient(original_client):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(transport=transport, **kwargs)

    monkeypatch.setattr(jama_client_module.httpx, "Client", MockHttpClient)
    client = JamaClient(_configured_settings(), JamaApiCredentials("cid", "secret"))
    monkeypatch.setattr(client, "_auth_headers", lambda _: {"Authorization": "Bearer token"})

    if patch_status == 200:
        updated = client.update_description(101, "Updated")
        assert updated.id == 101
        assert [request.method for request in requests] == ["GET", "GET", "PATCH", "GET"]
    else:
        with pytest.raises(JamaServiceError) as error:
            client.update_description(101, "Updated")
        assert error.value.message == (
            f"Jama API returned HTTP {patch_status} for PATCH items/101. "
            "The requested field cannot be updated."
        )
        assert error.value.detail["jama_status_code"] == patch_status
        assert error.value.detail["operation"] == "items/101"
        assert error.value.detail["request_method"] == "PATCH"
        assert error.value.detail["request_content_type"] == "application/json"
        assert error.value.detail["response_content_type"] == "application/json"
        assert error.value.detail["jama_message"] == "The requested field cannot be updated."
        assert "Private upstream response" not in str(error.value.detail)
        assert [request.method for request in requests] == ["GET", "GET", "PATCH"]

    patch_request = next(request for request in requests if request.method == "PATCH")
    assert patch_request.headers["content-type"] == "application/json"
    assert json.loads(patch_request.read()) == [
        {
            "op": "replace",
            "path": "/fields/description",
            "value": plain_text_to_jama_html("Updated"),
        }
    ]


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
    assert data["rationale"] == "To ensure adequate stopping distance."
    assert data["web_url"].endswith("/items/101?projectId=1")


@pytest.mark.unit
def test_endpoints_report_not_configured(client: TestClient) -> None:
    # No stub installed and test settings leave Jama unconfigured.
    response = client.get("/api/v1/jama/projects")
    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "JAMA_NOT_CONFIGURED"
