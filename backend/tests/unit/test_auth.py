"""
Authentication and authorization tests for Microsoft Entra ID.

These run the production validation path end to end - RS256 signature against a
JWKS document, issuer, audience, expiry, tenant, delegated scope, and app roles -
through the real FastAPI routing, with only the signing-key download replaced.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import EntraIDSettings
from app.core.security import (
    AuthenticatedUser,
    AuthProviderUnavailableError,
    EntraTokenValidator,
    Role,
    expand_roles,
)

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

TENANT = "11111111-1111-1111-1111-111111111111"
CLIENT = "22222222-2222-2222-2222-222222222222"

USER = ["Radia.User"]
DOC_ADMIN = ["Radia.DocumentAdmin"]
ADMIN = ["Radia.Admin"]


def _validator(entra_tokens, **settings_overrides) -> EntraTokenValidator:
    settings = EntraIDSettings(tenant_id=TENANT, client_id=CLIENT, **settings_overrides)
    return EntraTokenValidator(settings, jwks_fetcher=entra_tokens.jwks)


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_valid_v2_token_is_accepted(entra_tokens) -> None:
    claims = _validator(entra_tokens).validate(entra_tokens.token())

    assert claims["oid"] == "user-alice"
    assert claims["tid"] == TENANT


@pytest.mark.unit
def test_valid_v1_token_is_accepted(entra_tokens) -> None:
    claims = _validator(entra_tokens).validate(entra_tokens.token(version="1.0"))

    assert claims["aud"] == f"api://{CLIENT}"


@pytest.mark.unit
def test_expired_token_is_rejected(entra_tokens) -> None:
    token = entra_tokens.token(expires_in=-600)

    with pytest.raises(jwt.ExpiredSignatureError):
        _validator(entra_tokens).validate(token)


@pytest.mark.unit
def test_not_yet_valid_token_is_rejected(entra_tokens) -> None:
    token = entra_tokens.token(nbf=int(time.time()) + 3600)

    with pytest.raises(jwt.ImmatureSignatureError):
        _validator(entra_tokens).validate(token)


@pytest.mark.unit
def test_token_for_another_api_is_rejected(entra_tokens) -> None:
    token = entra_tokens.token(aud="api://some-other-api")

    with pytest.raises(jwt.InvalidAudienceError):
        _validator(entra_tokens).validate(token)


@pytest.mark.unit
def test_token_from_another_issuer_is_rejected(entra_tokens) -> None:
    token = entra_tokens.token(iss="https://login.microsoftonline.com/evil-tenant/v2.0")

    with pytest.raises(jwt.InvalidIssuerError):
        _validator(entra_tokens).validate(token)


@pytest.mark.unit
def test_tenant_claim_must_match_configured_tenant(entra_tokens) -> None:
    token = entra_tokens.token(tid="33333333-3333-3333-3333-333333333333")

    with pytest.raises(jwt.InvalidTokenError, match="different tenant"):
        _validator(entra_tokens).validate(token)


@pytest.mark.unit
def test_token_signed_by_untrusted_key_is_rejected(entra_tokens) -> None:
    forged_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = entra_tokens.token(signing_key=forged_key)

    with pytest.raises(jwt.InvalidSignatureError):
        _validator(entra_tokens).validate(token)


@pytest.mark.unit
def test_tampered_payload_is_rejected(entra_tokens) -> None:
    header, payload, signature = entra_tokens.token(roles=USER).split(".")
    admin_payload = entra_tokens.token(roles=ADMIN).split(".")[1]

    with pytest.raises(jwt.InvalidSignatureError):
        _validator(entra_tokens).validate(f"{header}.{admin_payload}.{signature}")


@pytest.mark.unit
def test_symmetric_algorithm_confusion_is_rejected(entra_tokens) -> None:
    token = jwt.encode(
        {"aud": CLIENT, "tid": TENANT, "oid": "x"},
        "shared-secret-value-long-enough-for-hs256",
        algorithm="HS256",
        headers={"kid": entra_tokens.kid},
    )

    with pytest.raises(jwt.InvalidAlgorithmError):
        _validator(entra_tokens).validate(token)


@pytest.mark.unit
def test_unsigned_token_is_rejected(entra_tokens) -> None:
    token = jwt.encode({"aud": CLIENT, "tid": TENANT}, None, algorithm="none")

    with pytest.raises(jwt.InvalidAlgorithmError):
        _validator(entra_tokens).validate(token)


@pytest.mark.unit
def test_delegated_token_without_api_scope_is_rejected(entra_tokens) -> None:
    token = entra_tokens.token(scp="User.Read")

    with pytest.raises(jwt.InvalidTokenError, match="required API scope"):
        _validator(entra_tokens).validate(token)


@pytest.mark.unit
def test_token_missing_object_id_is_rejected(entra_tokens) -> None:
    token = entra_tokens.token(oid=None)

    with pytest.raises(jwt.MissingRequiredClaimError):
        _validator(entra_tokens).validate(token)


@pytest.mark.unit
def test_unknown_key_id_refetch_is_rate_limited(entra_tokens) -> None:
    clock = [1000.0]
    validator = EntraTokenValidator(
        EntraIDSettings(tenant_id=TENANT, client_id=CLIENT),
        jwks_fetcher=entra_tokens.jwks,
        clock=lambda: clock[0],
    )
    validator.validate(entra_tokens.token())
    fetches_after_warmup = entra_tokens.jwks_fetch_count

    for _ in range(5):
        with pytest.raises(jwt.InvalidTokenError, match="signing key"):
            validator.validate(entra_tokens.token(kid="rotated-or-forged"))
    assert entra_tokens.jwks_fetch_count == fetches_after_warmup

    clock[0] += 301
    with pytest.raises(jwt.InvalidTokenError):
        validator.validate(entra_tokens.token(kid="rotated-or-forged"))
    assert entra_tokens.jwks_fetch_count == fetches_after_warmup + 1


@pytest.mark.unit
def test_signing_keys_unreachable_without_cache_reports_unavailable() -> None:
    def failing_fetch() -> dict:
        raise ConnectionError("login.microsoftonline.com unreachable")

    validator = EntraTokenValidator(
        EntraIDSettings(tenant_id=TENANT, client_id=CLIENT), jwks_fetcher=failing_fetch
    )
    token = jwt.encode(
        {"a": 1},
        rsa.generate_private_key(public_exponent=65537, key_size=2048),
        algorithm="RS256",
        headers={"kid": "k"},
    )

    with pytest.raises(AuthProviderUnavailableError):
        validator.validate(token)


@pytest.mark.unit
def test_cached_keys_survive_refresh_failure(entra_tokens) -> None:
    clock = [0.0]
    calls = {"n": 0}

    def flaky_fetch() -> dict:
        calls["n"] += 1
        if calls["n"] > 1:
            raise ConnectionError("temporary outage")
        return entra_tokens.jwks()

    validator = EntraTokenValidator(
        EntraIDSettings(tenant_id=TENANT, client_id=CLIENT, jwks_cache_ttl_seconds=60),
        jwks_fetcher=flaky_fetch,
        clock=lambda: clock[0],
    )
    validator.validate(entra_tokens.token())
    clock[0] += 3600

    assert validator.validate(entra_tokens.token())["oid"] == "user-alice"


@pytest.mark.unit
def test_role_hierarchy() -> None:
    assert expand_roles([Role.ADMIN]) == {Role.ADMIN, Role.DOCUMENT_ADMIN, Role.USER}
    assert expand_roles([Role.DOCUMENT_ADMIN]) == {Role.DOCUMENT_ADMIN, Role.USER}
    assert expand_roles([Role.USER]) == {Role.USER}
    assert expand_roles(["Something.Else"]) == {"Something.Else"}


@pytest.mark.unit
def test_user_from_claims_collects_identity_aliases() -> None:
    user = AuthenticatedUser.from_claims(
        {
            "oid": "o",
            "tid": "t",
            "scp": "access_as_user",
            "preferred_username": "A.Person@Corp.example",
            "email": "alias@corp.example",
            "roles": ["Radia.User"],
        }
    )

    assert user.email == "alias@corp.example"
    assert user.identity_names == {"alias@corp.example", "a.person@corp.example"}
    assert user.subject_key == "t:o"
    assert user.is_app is False


# ---------------------------------------------------------------------------
# Route protection
# ---------------------------------------------------------------------------

PROTECTED_USER_ROUTES = [
    ("GET", "/api/v1/auth/me"),
    ("GET", "/api/v1/standards"),
    ("POST", "/api/v1/search"),
    ("POST", "/api/v1/chat"),
    ("POST", "/api/v1/chat/stream"),
    ("GET", "/api/v1/documents"),
    ("GET", "/api/v1/documents/some-doc"),
    ("GET", "/api/v1/review/version"),
    ("POST", "/api/v1/review/requirement"),
    ("POST", "/api/v1/review/delta"),
    ("GET", "/api/v1/review/history"),
    ("POST", "/api/v1/review/history/rev-1/disposition"),
    ("GET", "/api/v1/jama/account"),
    ("PUT", "/api/v1/jama/account"),
    ("DELETE", "/api/v1/jama/account"),
    ("GET", "/api/v1/jama/projects"),
    ("GET", "/api/v1/jama/requirements"),
    ("GET", "/api/v1/jama/requirements/1"),
    ("GET", "/api/v1/ingest/status"),
]

DOCUMENT_ADMIN_ROUTES = [
    ("POST", "/api/v1/ingest"),
    ("POST", "/api/v1/ingest/upload"),
    ("GET", f"/api/v1/ingest/jobs/{uuid4()}"),
    ("POST", "/api/v1/ingest/webhook/subscribe"),
    ("DELETE", "/api/v1/documents/some-doc"),
]


@pytest.mark.unit
@pytest.mark.parametrize(("method", "path"), PROTECTED_USER_ROUTES + DOCUMENT_ADMIN_ROUTES)
def test_protected_routes_require_a_token(
    secured_client: TestClient, method: str, path: str
) -> None:
    response = secured_client.request(method, path)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Bearer")
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.unit
@pytest.mark.parametrize(
    "header",
    ["Bearer not-a-jwt", "Bearer ", "Basic dXNlcjpwYXNz", "Bearer a.b.c"],
)
def test_malformed_credentials_are_rejected(secured_client: TestClient, header: str) -> None:
    response = secured_client.get("/api/v1/auth/me", headers={"Authorization": header})

    assert response.status_code == 401


@pytest.mark.unit
def test_expired_token_is_rejected_by_api(secured_client: TestClient, entra_tokens) -> None:
    response = secured_client.get("/api/v1/auth/me", headers=entra_tokens.headers(expires_in=-600))

    assert response.status_code == 401


@pytest.mark.unit
def test_signed_in_user_without_radia_role_is_forbidden(
    secured_client: TestClient, entra_tokens
) -> None:
    response = secured_client.get("/api/v1/standards", headers=entra_tokens.headers(roles=[]))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.unit
def test_app_only_tokens_are_rejected_by_default(secured_client: TestClient, entra_tokens) -> None:
    response = secured_client.get(
        "/api/v1/standards", headers=entra_tokens.headers(scp=None, roles=ADMIN)
    )

    assert response.status_code == 403


@pytest.mark.unit
def test_me_returns_verified_identity_and_effective_roles(
    secured_client: TestClient, entra_tokens
) -> None:
    response = secured_client.get("/api/v1/auth/me", headers=entra_tokens.headers(roles=DOC_ADMIN))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user_id"] == "user-alice"
    assert data["email"] == "alice@radia.example"
    assert data["auth_method"] == "entra"
    assert data["roles"] == ["Radia.DocumentAdmin", "Radia.User"]
    assert data["can_manage_documents"] is True
    assert data["is_admin"] is False


@pytest.mark.unit
def test_radia_user_can_use_the_app(secured_client: TestClient, entra_tokens) -> None:
    response = secured_client.get("/api/v1/standards", headers=entra_tokens.headers(roles=USER))

    assert response.status_code == 200


@pytest.mark.unit
@pytest.mark.parametrize(("method", "path"), DOCUMENT_ADMIN_ROUTES)
def test_ingestion_management_requires_document_admin(
    secured_client: TestClient, entra_tokens, method: str, path: str
) -> None:
    response = secured_client.request(method, path, headers=entra_tokens.headers(roles=USER))

    assert response.status_code == 403
    assert "Radia.DocumentAdmin" in response.json()["error"]["detail"]["required_roles"]


@pytest.mark.unit
@pytest.mark.parametrize("roles", [DOC_ADMIN, ADMIN])
def test_document_admins_pass_ingestion_authorization(
    secured_client: TestClient, entra_tokens, roles: list[str]
) -> None:
    from radia_ai.features.jama_requirement_reviewer.dependencies.container import (
        get_ingestion_job_store,
    )

    app = secured_client.app
    app.dependency_overrides[get_ingestion_job_store] = _RecordingJobStore
    try:
        response = secured_client.post(
            "/api/v1/ingest", json={"source": "blob"}, headers=entra_tokens.headers(roles=roles)
        )
    finally:
        app.dependency_overrides.pop(get_ingestion_job_store, None)

    assert response.status_code == 202


@pytest.mark.unit
def test_health_probes_stay_public(secured_client: TestClient) -> None:
    assert secured_client.get("/api/v1/health/live").status_code == 200


@pytest.mark.unit
def test_graph_webhook_does_not_require_a_user_token(secured_client: TestClient) -> None:
    response = secured_client.post("/api/v1/ingest/webhook?validationToken=handshake-123")

    assert response.status_code == 200
    assert response.text == "handshake-123"


@pytest.mark.unit
def test_graph_webhook_rejects_notifications_failing_client_state(
    secured_client: TestClient,
) -> None:
    class _RejectingWebhook:
        def handle_notification(self, notifications: list) -> bool:
            return False

    from radia_ai.features.jama_requirement_reviewer.dependencies.container import (
        get_sharepoint_webhook_service,
    )

    app = secured_client.app
    app.dependency_overrides[get_sharepoint_webhook_service] = lambda: _RejectingWebhook()
    try:
        response = secured_client.post(
            "/api/v1/ingest/webhook", json={"value": [{"clientState": "forged"}]}
        )
    finally:
        app.dependency_overrides.pop(get_sharepoint_webhook_service, None)

    assert response.status_code == 401


@pytest.mark.unit
def test_auth_not_configured_fails_closed_in_deployed_environments(
    test_app, client: TestClient
) -> None:
    from app.core.config import get_settings

    settings = test_app.state.settings.model_copy(update={"environment": "development"})
    previous = test_app.dependency_overrides[get_settings]
    test_app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = client.get("/api/v1/standards")
    finally:
        test_app.dependency_overrides[get_settings] = previous

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AUTH_NOT_CONFIGURED"


@pytest.mark.unit
def test_missing_environment_defaults_to_production_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import AppSettings
    from app.main import StartupConfigurationError, _validate_auth_configuration

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    settings = AppSettings.model_construct()

    assert settings.environment == "production"
    assert settings.allows_local_auth_bypass is False
    with pytest.raises(StartupConfigurationError):
        _validate_auth_configuration(settings)


@pytest.mark.unit
def test_production_refuses_to_start_without_entra(test_settings) -> None:
    from app.main import StartupConfigurationError, _validate_auth_configuration

    production = test_settings.model_copy(update={"environment": "production", "debug": False})

    with pytest.raises(StartupConfigurationError, match="Entra ID authentication is required"):
        _validate_auth_configuration(production)


# ---------------------------------------------------------------------------
# Review history ownership
# ---------------------------------------------------------------------------


def _run_review(client: TestClient, headers: dict[str, str], requirement_id: str) -> str:
    response = client.post(
        "/api/v1/review/requirement",
        json={"requirement_id": requirement_id, "text": "The subsystem should respond fast."},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()["data"]["review_id"]


@pytest.mark.unit
def test_review_history_is_private_to_its_owner(secured_client: TestClient, entra_tokens) -> None:
    alice = entra_tokens.headers(oid="user-alice", email="alice@radia.example")
    bob = entra_tokens.headers(oid="user-bob", email="bob@radia.example", name="Bob")
    alice_review = _run_review(secured_client, alice, "REQ-ALICE")
    bob_review = _run_review(secured_client, bob, "REQ-BOB")

    alice_history = secured_client.get("/api/v1/review/history", headers=alice).json()["data"]
    bob_history = secured_client.get("/api/v1/review/history", headers=bob).json()["data"]

    assert [e["review_id"] for e in alice_history["entries"]] == [alice_review]
    assert [e["review_id"] for e in bob_history["entries"]] == [bob_review]
    assert alice_history["entries"][0]["owner_name"] == "Alice Engineer"


@pytest.mark.unit
def test_admin_sees_every_users_review_history(secured_client: TestClient, entra_tokens) -> None:
    alice = entra_tokens.headers(oid="user-alice")
    admin = entra_tokens.headers(oid="user-admin", email="admin@radia.example", roles=ADMIN)
    alice_review = _run_review(secured_client, alice, "REQ-ALICE")

    everyone = secured_client.get("/api/v1/review/history", headers=admin).json()["data"]
    mine = secured_client.get("/api/v1/review/history?mine_only=true", headers=admin).json()["data"]

    assert alice_review in [e["review_id"] for e in everyone["entries"]]
    assert mine["entries"] == []


@pytest.mark.unit
def test_users_cannot_disposition_someone_elses_review(
    secured_client: TestClient, entra_tokens
) -> None:
    alice = entra_tokens.headers(oid="user-alice")
    bob = entra_tokens.headers(oid="user-bob", email="bob@radia.example")
    alice_review = _run_review(secured_client, alice, "REQ-ALICE")

    response = secured_client.post(
        f"/api/v1/review/history/{alice_review}/disposition",
        json={"finding_index": 0, "disposition": "Rejected"},
        headers=bob,
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Review ID not found in history."


@pytest.mark.unit
def test_disposition_reviewer_is_taken_from_the_token(
    secured_client: TestClient, entra_tokens
) -> None:
    alice = entra_tokens.headers(oid="user-alice", email="alice@radia.example")
    review_id = _run_review(secured_client, alice, "REQ-ALICE")

    response = secured_client.post(
        f"/api/v1/review/history/{review_id}/disposition",
        json={"finding_index": 0, "disposition": "Accepted", "reviewer_id": "spoofed@evil"},
        headers=alice,
    )

    assert response.status_code == 200
    assert response.json()["data"]["dispositions"][0]["reviewer_id"] == "alice@radia.example"


class _RecordingJobStore:
    def enqueue(self, **kwargs: object) -> tuple[dict[str, str], bool]:
        return {"job_id": str(uuid4()), "message": "queued"}, True
