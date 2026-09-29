"""Mock HTTP plumbing and sample payloads for the Jama tests.

Nothing here touches the network: every Jama response is served by an
``httpx2.MockTransport`` handler, and each handler records the requests it saw
so tests can assert on the URL, query string and auth header actually sent.
"""

from collections.abc import Callable
from typing import Any

import httpx2

from mcp_radia.connectors.jama import JamaClient, JamaSettings

# -- sample payloads ---------------------------------------------------------

ITEM_PAYLOAD: dict[str, Any] = {
    "meta": {"status": "OK"},
    "data": {
        "id": 12345,
        "documentKey": "SRS-42",
        "globalId": "GID-987",
        "project": 7,
        "itemType": 31,
        "createdDate": "2026-01-05T10:00:00.000+0000",
        "modifiedDate": "2026-02-11T14:30:00.000+0000",
        "fields": {
            "name": "Battery shall report state of charge",
            "description": (
                "<p>The battery <b>shall</b> report state of charge.</p>"
                "<p>Accuracy &gt; 98&#37;.</p>"
            ),
            "status": "Approved",
            "customField123": "traced-to-JIRA-451",
        },
    },
}

SEARCH_PAYLOAD: dict[str, Any] = {
    "meta": {
        "status": "OK",
        "pageInfo": {"startIndex": 0, "resultCount": 2, "totalResults": 137},
    },
    "data": [
        {
            "id": 12345,
            "documentKey": "SRS-42",
            "globalId": "GID-987",
            "project": 7,
            "itemType": 31,
            "fields": {"name": "Battery shall report state of charge"},
        },
        {
            "id": 12346,
            "documentKey": "SRS-43",
            "project": 7,
            "itemType": 31,
            "fields": {"name": "Battery shall report cell temperature"},
        },
    ],
}

TOKEN_PAYLOAD: dict[str, Any] = {"access_token": "tok-abc123", "expires_in": 3600}


# -- settings builders -------------------------------------------------------


def basic_settings(**overrides: Any) -> JamaSettings:
    """Fully configured basic-auth settings. ``_env_file=None`` keeps a
    developer's real mcp-radia/.env from leaking into the tests."""
    values: dict[str, Any] = {
        "base_url": "https://example.jamacloud.com",
        "auth_type": "basic",
        "username": "api-id",
        "password": "api-key",
    }
    values.update(overrides)
    return JamaSettings(_env_file=None, **values)


def oauth_settings(**overrides: Any) -> JamaSettings:
    values: dict[str, Any] = {
        "base_url": "https://example.jamacloud.com",
        "auth_type": "oauth",
        "client_id": "cid",
        "client_secret": "csecret",
    }
    values.update(overrides)
    return JamaSettings(_env_file=None, **values)


# -- mock transport ----------------------------------------------------------


class RecordingHandler:
    """A MockTransport handler that records requests and replays canned responses."""

    def __init__(self, responder: Callable[[httpx2.Request], httpx2.Response]) -> None:
        self._responder = responder
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self._responder(request)

    @property
    def last_request(self) -> httpx2.Request:
        return self.requests[-1]


def make_client(
    settings: JamaSettings,
    responder: Callable[[httpx2.Request], httpx2.Response],
) -> tuple[JamaClient, RecordingHandler]:
    """Build a JamaClient whose HTTP goes to ``responder`` instead of the network."""
    handler = RecordingHandler(responder)
    http_client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return JamaClient(settings, client=http_client), handler


def json_responder(
    payload: Any,
    status_code: int = 200,
) -> Callable[[httpx2.Request], httpx2.Response]:
    """Always answer with the same JSON body."""

    def _respond(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status_code, json=payload, request=request)

    return _respond


def routed_responder(
    routes: dict[str, tuple[int, Any]],
) -> Callable[[httpx2.Request], httpx2.Response]:
    """Answer based on a substring match against the request path.

    Lets one handler serve both the OAuth token endpoint and the REST endpoint.
    """

    def _respond(request: httpx2.Request) -> httpx2.Response:
        for fragment, (status, payload) in routes.items():
            if fragment in request.url.path:
                return httpx2.Response(status, json=payload, request=request)
        return httpx2.Response(404, json={"meta": {"status": "Not Found"}}, request=request)

    return _respond
