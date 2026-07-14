"""
Unit tests for chat endpoint.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_chat_returns_200(client: TestClient) -> None:
    response = client.post(
        "/api/v1/chat",
        json={"question": "What are the system requirements?"},
    )
    assert response.status_code == 200


@pytest.mark.unit
def test_chat_response_structure(client: TestClient) -> None:
    response = client.post(
        "/api/v1/chat",
        json={"question": "What are the system requirements?"},
    )
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert "answer" in data
    assert "citations" in data
    assert "model" in data
    assert "retrieval_count" in data


@pytest.mark.unit
def test_chat_rejects_empty_question(client: TestClient) -> None:
    response = client.post("/api/v1/chat", json={"question": ""})
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.unit
def test_chat_with_history(client: TestClient) -> None:
    response = client.post(
        "/api/v1/chat",
        json={
            "question": "Follow-up question?",
            "conversation_history": [
                {"role": "user", "content": "First question"},
                {"role": "assistant", "content": "First answer"},
            ],
        },
    )
    assert response.status_code == 200
