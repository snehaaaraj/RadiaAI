"""
Per-user Jama account linking tests.

A fake Jama Connect server (``httpx.MockTransport``) stands in for Jama so the
real client code path runs: OAuth client-credentials token exchange, bearer
header, token caching, ``/users/current`` identity lookup, and error mapping.
Each fake Jama user sees a different set of projects, which proves calls are
made *as the signed-in user* rather than as a shared service account.
"""

from __future__ import annotations

import base64
import types
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from cryptography.fernet import Fernet

from app.core.config import JamaSettings, get_settings
from app.core.exceptions import JamaAccountNotLinkedError, JamaNotConfiguredError
from app.core.security import AuthenticatedUser
from radia_ai.features.jama_requirement_reviewer.connectors import jama_client as jama_client_module
from radia_ai.features.jama_requirement_reviewer.connectors.jama_client import (
    JamaApiCredentials,
    JamaClient,
    JamaTokenCache,
)
from radia_ai.features.jama_requirement_reviewer.models.jama_models import JamaUserProfile
from radia_ai.features.jama_requirement_reviewer.repositories.jama_credential_repository import (
    JamaCredentialRepository,
)
from radia_ai.features.jama_requirement_reviewer.services.jama_account_service import (
    JamaAccountService,
)
from radia_ai.features.jama_requirement_reviewer.services.jama_service import JamaService

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

JAMA_URL = "https://jama.test"


class MemoryBlobStore:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    def upload_blob(
        self, blob_name: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        self.blobs[blob_name] = data
        return blob_name

    def download_blob(self, blob_name: str) -> bytes:
        return self.blobs[blob_name]

    def delete_blob(self, blob_name: str) -> None:
        self.blobs.pop(blob_name, None)


class FakeJama:
    """Minimal Jama Connect REST API with per-user project visibility."""

    def __init__(self) -> None:
        self.accounts: dict[str, dict[str, Any]] = {
            "alice-client": {
                "secret": "alice-secret",
                "profile": {
                    "id": 10,
                    "username": "alice",
                    "email": "Alice@Radia.example",
                    "firstName": "Alice",
                    "lastName": "Engineer",
                    "active": True,
                },
                "projects": [1],
            },
            "bob-client": {
                "secret": "bob-secret",
                "profile": {"id": 20, "username": "bob", "email": "bob@radia.example"},
                "projects": [2],
            },
        }
        self.token_requests = 0
        self.api_auth_headers: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rest/oauth/token":
            return self._token(request)
        header = request.headers.get("Authorization", "")
        self.api_auth_headers.append(header)
        account = self._account_for_bearer(header)
        if account is None:
            return httpx.Response(401)
        path = request.url.path.removeprefix("/rest/v1/")
        if path == "users/current":
            return httpx.Response(200, json={"data": account["profile"]})
        if path == "projects":
            data = [
                {"id": pid, "projectKey": f"P{pid}", "fields": {"name": f"Project {pid}"}}
                for pid in account["projects"]
            ]
            return httpx.Response(200, json={"data": data})
        if path.startswith("items/"):
            item_id = int(path.split("/")[1])
            project_id = item_id // 100
            if project_id not in account["projects"]:
                return httpx.Response(403)
            return httpx.Response(
                200,
                json={"data": {"id": item_id, "project": project_id, "fields": {"name": "Req"}}},
            )
        return httpx.Response(404)

    def _token(self, request: httpx.Request) -> httpx.Response:
        self.token_requests += 1
        encoded = request.headers.get("Authorization", "").removeprefix("Basic ")
        client_id, _, secret = base64.b64decode(encoded).decode().partition(":")
        account = self.accounts.get(client_id)
        if account is None or account["secret"] != secret:
            return httpx.Response(401, json={"error": "invalid_client"})
        return httpx.Response(
            200,
            json={"access_token": f"tok-{client_id}", "token_type": "bearer", "expires_in": 3599},
        )

    def _account_for_bearer(self, header: str) -> dict[str, Any] | None:
        if not header.startswith("Bearer tok-"):
            return None
        return self.accounts.get(header.removeprefix("Bearer tok-"))


@pytest.fixture
def fake_jama(monkeypatch: pytest.MonkeyPatch) -> FakeJama:
    server = FakeJama()
    transport = httpx.MockTransport(server.handler)
    fake_httpx = types.SimpleNamespace(
        BasicAuth=httpx.BasicAuth,
        HTTPError=httpx.HTTPError,
        HTTPStatusError=httpx.HTTPStatusError,
        Client=lambda **kwargs: httpx.Client(transport=transport, **kwargs),
    )
    monkeypatch.setattr(jama_client_module, "httpx", fake_httpx)
    return server


@pytest.fixture
def encryption_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def jama_app(secured_app, fake_jama: FakeJama, encryption_key: str):
    """Secured app with per-user Jama linking enabled and no shared Jama account."""
    settings = secured_app.state.settings.model_copy(
        update={
            "jama": JamaSettings(
                base_url=JAMA_URL,
                auth_type="basic",
                username="",
                password="",
                client_id="",
                client_secret="",
                credential_encryption_key=encryption_key,
            )
        }
    )
    secured_app.dependency_overrides[get_settings] = lambda: settings
    secured_app.state.settings = settings
    store = MemoryBlobStore()
    secured_app.state.jama_credential_repository = JamaCredentialRepository(store, encryption_key)
    secured_app.state.jama_token_cache = JamaTokenCache()
    secured_app.state.jama_blob_store = store
    yield secured_app
    for attribute in ("jama_credential_repository", "jama_token_cache", "jama_blob_store"):
        delattr(secured_app.state, attribute)


@pytest.fixture
def jama_client(jama_app) -> TestClient:
    from fastapi.testclient import TestClient

    return TestClient(jama_app)


def _alice(entra_tokens) -> dict[str, str]:
    return entra_tokens.headers(oid="user-alice", email="alice@radia.example")


def _bob(entra_tokens) -> dict[str, str]:
    return entra_tokens.headers(oid="user-bob", email="bob@radia.example", name="Bob")


def _link(client: TestClient, headers: dict[str, str], client_id: str, secret: str):
    return client.put(
        "/api/v1/jama/account",
        json={"client_id": client_id, "client_secret": secret},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Linking flow
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_unlinked_user_is_told_to_link_before_using_jama(jama_client, entra_tokens) -> None:
    status = jama_client.get("/api/v1/jama/account", headers=_alice(entra_tokens))
    projects = jama_client.get("/api/v1/jama/projects", headers=_alice(entra_tokens))

    assert status.status_code == 200
    assert status.json()["data"]["linked"] is False
    assert status.json()["data"]["linking_enabled"] is True
    assert status.json()["data"]["using_shared_account"] is False
    assert projects.status_code == 403
    assert projects.json()["error"]["code"] == "JAMA_ACCOUNT_NOT_LINKED"


@pytest.mark.unit
def test_linking_verifies_credentials_with_jama(jama_client, entra_tokens) -> None:
    response = _link(jama_client, _alice(entra_tokens), "alice-client", "wrong-secret")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "JAMA_CREDENTIALS_INVALID"
    assert jama_client.app.state.jama_blob_store.blobs == {}


@pytest.mark.unit
def test_cannot_link_someone_elses_jama_account(jama_client, entra_tokens) -> None:
    response = _link(jama_client, _alice(entra_tokens), "bob-client", "bob-secret")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "JAMA_ACCOUNT_MISMATCH"
    assert jama_client.app.state.jama_blob_store.blobs == {}


@pytest.mark.unit
def test_link_succeeds_and_never_echoes_the_secret(jama_client, entra_tokens) -> None:
    response = _link(jama_client, _alice(entra_tokens), " alice-client ", "alice-secret")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["linked"] is True
    assert data["jama_user_id"] == 10
    assert data["jama_email"] == "Alice@Radia.example"
    assert data["jama_display_name"] == "Alice Engineer"
    assert data["linked_at"]
    assert "alice-secret" not in response.text

    status = jama_client.get("/api/v1/jama/account", headers=_alice(entra_tokens)).json()["data"]
    assert status["linked"] is True and status["jama_username"] == "alice"


@pytest.mark.unit
def test_stored_credentials_are_encrypted_and_not_keyed_by_user_id(
    jama_client, entra_tokens
) -> None:
    _link(jama_client, _alice(entra_tokens), "alice-client", "alice-secret")

    blobs = jama_client.app.state.jama_blob_store.blobs
    assert len(blobs) == 1
    ((name, content),) = blobs.items()
    assert "user-alice" not in name
    assert b"alice-secret" not in content
    assert b"alice-client" not in content


@pytest.mark.unit
def test_each_user_sees_only_their_own_jama_projects(jama_client, entra_tokens) -> None:
    assert (
        _link(jama_client, _alice(entra_tokens), "alice-client", "alice-secret").status_code == 200
    )
    assert _link(jama_client, _bob(entra_tokens), "bob-client", "bob-secret").status_code == 200

    alice_projects = jama_client.get("/api/v1/jama/projects", headers=_alice(entra_tokens))
    bob_projects = jama_client.get("/api/v1/jama/projects", headers=_bob(entra_tokens))

    assert [p["id"] for p in alice_projects.json()["data"]["projects"]] == [1]
    assert [p["id"] for p in bob_projects.json()["data"]["projects"]] == [2]


@pytest.mark.unit
def test_jama_permission_denial_is_surfaced(jama_client, entra_tokens, fake_jama) -> None:
    _link(jama_client, _alice(entra_tokens), "alice-client", "alice-secret")

    allowed = jama_client.get("/api/v1/jama/requirements/105", headers=_alice(entra_tokens))
    denied = jama_client.get("/api/v1/jama/requirements/205", headers=_alice(entra_tokens))

    assert allowed.status_code == 200
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "JAMA_PERMISSION_DENIED"
    assert all(h == "Bearer tok-alice-client" for h in fake_jama.api_auth_headers)


@pytest.mark.unit
def test_jama_tokens_are_cached_across_requests(jama_client, entra_tokens, fake_jama) -> None:
    _link(jama_client, _alice(entra_tokens), "alice-client", "alice-secret")
    requests_after_link = fake_jama.token_requests

    for _ in range(3):
        jama_client.get("/api/v1/jama/projects", headers=_alice(entra_tokens))

    assert requests_after_link == 1
    assert fake_jama.token_requests == 1


@pytest.mark.unit
def test_revoked_jama_credentials_prompt_relink(jama_client, entra_tokens, fake_jama) -> None:
    _link(jama_client, _alice(entra_tokens), "alice-client", "alice-secret")
    del fake_jama.accounts["alice-client"]

    response = jama_client.get("/api/v1/jama/projects", headers=_alice(entra_tokens))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "JAMA_CREDENTIALS_INVALID"


@pytest.mark.unit
def test_unlink_removes_access(jama_client, entra_tokens) -> None:
    _link(jama_client, _alice(entra_tokens), "alice-client", "alice-secret")

    response = jama_client.delete("/api/v1/jama/account", headers=_alice(entra_tokens))
    projects = jama_client.get("/api/v1/jama/projects", headers=_alice(entra_tokens))

    assert response.status_code == 200
    assert response.json()["data"]["linked"] is False
    assert jama_client.app.state.jama_blob_store.blobs == {}
    assert projects.json()["error"]["code"] == "JAMA_ACCOUNT_NOT_LINKED"


@pytest.mark.unit
def test_link_request_validation(jama_client, entra_tokens) -> None:
    response = jama_client.put(
        "/api/v1/jama/account",
        json={"client_id": "", "client_secret": ""},
        headers=_alice(entra_tokens),
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Credential repository
# ---------------------------------------------------------------------------

_PROFILE = JamaUserProfile(id=1, username="alice", email="alice@radia.example")


@pytest.mark.unit
def test_credentials_copied_to_another_user_cannot_be_used(encryption_key: str) -> None:
    store = MemoryBlobStore()
    repository = JamaCredentialRepository(store, encryption_key)
    repository.save("tenant:alice", JamaApiCredentials("alice-client", "alice-secret"), _PROFILE)
    ((alice_blob, content),) = store.blobs.items()
    store.blobs[JamaCredentialRepository._blob_name("tenant:mallory")] = content

    assert repository.get_credentials("tenant:mallory") is None
    assert repository.get_credentials("tenant:alice") == JamaApiCredentials(
        "alice-client", "alice-secret"
    )


@pytest.mark.unit
def test_encryption_key_rotation_keeps_existing_links_readable(encryption_key: str) -> None:
    store = MemoryBlobStore()
    JamaCredentialRepository(store, encryption_key).save(
        "tenant:alice", JamaApiCredentials("alice-client", "alice-secret"), _PROFILE
    )
    new_key = Fernet.generate_key().decode()

    rotated = JamaCredentialRepository(store, f"{new_key},{encryption_key}")
    retired = JamaCredentialRepository(store, new_key)

    assert rotated.get_credentials("tenant:alice") is not None
    assert retired.get_credentials("tenant:alice") is None


@pytest.mark.unit
def test_invalid_encryption_key_is_a_configuration_error() -> None:
    from app.core.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError):
        JamaCredentialRepository(MemoryBlobStore(), "not-a-fernet-key")


@pytest.mark.unit
def test_credentials_repr_hides_the_secret() -> None:
    assert "alice-secret" not in repr(JamaApiCredentials("alice-client", "alice-secret"))


# ---------------------------------------------------------------------------
# Shared service account is local-only
# ---------------------------------------------------------------------------


def _shared_settings(test_settings, environment: str):
    return test_settings.model_copy(
        update={
            "environment": environment,
            "jama": JamaSettings(
                base_url=JAMA_URL,
                auth_type="oauth",
                username="",
                password="",
                client_id="svc",
                client_secret="svc-secret",
                credential_encryption_key="",
            ),
        }
    )


_USER = AuthenticatedUser(user_id="u", tenant_id="t", email="u@x", roles=frozenset({"Radia.User"}))


@pytest.mark.unit
@pytest.mark.parametrize("environment", ["development", "staging", "production"])
def test_shared_jama_account_is_never_used_in_deployed_environments(
    test_settings, environment: str
) -> None:
    settings = _shared_settings(test_settings, environment)
    shared = JamaService(JamaClient(settings.jama))
    service = JamaAccountService(settings, None, JamaTokenCache(), shared_service=shared)

    assert settings.allows_shared_jama_account is False
    with pytest.raises(JamaNotConfiguredError, match="linking is not enabled"):
        service.service_for(_USER)
    assert service.status(_USER).using_shared_account is False


@pytest.mark.unit
def test_shared_jama_account_is_allowed_for_local_development(test_settings) -> None:
    settings = _shared_settings(test_settings, "local")
    shared = JamaService(JamaClient(settings.jama))
    service = JamaAccountService(settings, None, JamaTokenCache(), shared_service=shared)

    assert service.service_for(_USER) is shared
    assert service.status(_USER).using_shared_account is True


@pytest.mark.unit
def test_shared_jama_account_is_not_used_once_sign_in_is_configured(test_settings) -> None:
    from app.core.config import EntraIDSettings

    settings = _shared_settings(test_settings, "local").model_copy(
        update={"entra": EntraIDSettings(tenant_id="t", client_id="c")}
    )

    assert settings.allows_shared_jama_account is False


@pytest.mark.unit
def test_unlinked_user_in_deployed_environment_gets_not_linked(
    test_settings, encryption_key: str
) -> None:
    settings = _shared_settings(test_settings, "production")
    repository = JamaCredentialRepository(MemoryBlobStore(), encryption_key)
    shared = JamaService(JamaClient(settings.jama))
    service = JamaAccountService(settings, repository, JamaTokenCache(), shared_service=shared)

    with pytest.raises(JamaAccountNotLinkedError):
        service.service_for(_USER)
