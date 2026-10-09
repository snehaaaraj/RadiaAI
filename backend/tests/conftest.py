"""
Test configuration - shared fixtures and test client setup.

pytest-asyncio is configured in auto mode (see pyproject.toml), so
async test functions work without explicit @pytest.mark.asyncio decorators.

Unit tests never reach Azure. The `review_engine` fixture is autouse and installs
a deterministic stand-in for the consolidated LLM enhancer, so the review pipeline
is exercised end-to-end without network access. Tests that need a specific engine
behaviour (a failure, a per-requirement outcome) call `review_engine.install(...)`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pytest
from azure.core.exceptions import ResourceNotFoundError
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# Application import creates the ASGI app, so identify this process as a test
# environment before importing it.
os.environ.setdefault("ENVIRONMENT", "test")

from app.core.config import AppSettings, get_settings
from app.main import create_app
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    ConsolidatedReviewResult,
    FindingSeverity,
    PassFail,
    RequirementReviewInput,
    RequirementRevision,
    ReviewCompletion,
    ReviewFinding,
    ReviewStatus,
)
from radia_ai.features.jama_requirement_reviewer.repositories.review_history_repository import (
    ReviewHistoryRepository,
)
from radia_ai.features.jama_requirement_reviewer.synthesis.recommendation_synthesizer import (
    RecommendationSynthesizer,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# Services cached on app.state that must be dropped when the engine is swapped,
# so the DI container rebuilds them against the new enhancer.
_CACHED_REVIEW_STATE = (
    "llm_enhancer",
    "recommendation_synthesizer",
    "review_orchestrator",
    "review_version_service",
    "requirement_review_service",
    "requirement_delta_review_service",
)


class InMemoryBlobClient:
    """In-memory drop-in for ``BlobStorageClient`` used in tests."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    def upload_blob(
        self, blob_name: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        self._blobs[blob_name] = data
        return f"https://test.blob.core.windows.net/test/{blob_name}"

    def download_blob(self, blob_name: str) -> bytes:
        if blob_name not in self._blobs:
            raise ResourceNotFoundError("Blob not found")
        return self._blobs[blob_name]

    def delete_blob(self, blob_name: str) -> None:
        self._blobs.pop(blob_name, None)

    def list_blobs(self, prefix: str = "") -> list[dict[str, Any]]:
        from datetime import UTC, datetime

        return [
            {
                "name": name,
                "size": len(data),
                "last_modified": datetime.now(UTC).isoformat(),
                "content_type": "application/json",
                "etag": None,
            }
            for name, data in self._blobs.items()
            if name.startswith(prefix)
        ]

    def probe(self) -> None:
        """Always succeeds - stands in for a healthy blob store in health checks."""
        return None


def build_stub_finding(
    *,
    reviewer: str = "language",
    category: str = "Ambiguous Wording",
    severity: FindingSeverity = FindingSeverity.MEDIUM,
    status: ReviewStatus = ReviewStatus.REVISION_RECOMMENDED,
) -> ReviewFinding:
    """Build a realistic finding for tests that need review output."""
    return ReviewFinding(
        category=category,
        reviewer=reviewer,
        severity=severity,
        pass_fail=PassFail.FAIL,
        status=status,
        rule="Requirements shall avoid subjective performance terms.",
        explanation="'fast' is not measurable and cannot be verified.",
        evidence="respond fast",
        recommendation="Replace 'fast' with a quantified response time.",
        reference="incose",
        reference_title="INCOSE Guide for Writing Requirements",
        suggested_rewrite="The subsystem shall respond within 100 ms under nominal load.",
    )


class StubLLMReviewEnhancer:
    """
    Deterministic stand-in for the Azure-backed consolidated review enhancer.

    Accepts a callable so a test can vary the result per requirement - needed to
    cover partially-failed delta runs. It mirrors the real enhancer's two modes:
    ``consolidated_review`` authors rewrites, ``score_revision`` only scores.
    """

    def __init__(
        self,
        result: ConsolidatedReviewResult
        | Callable[[RequirementReviewInput], ConsolidatedReviewResult],  # type: ignore[name-defined]
    ) -> None:
        self._result = result

    def consolidated_review(self, payload: RequirementReviewInput) -> ConsolidatedReviewResult:
        if callable(self._result):
            return self._result(payload)
        return self._result

    def score_revision(self, revision: RequirementRevision) -> ConsolidatedReviewResult:
        """Score a revision, stripping rewrites exactly as the real enhancer does."""
        result = self.consolidated_review(revision.requirement)
        return result.model_copy(
            update={
                "findings": [
                    finding.model_copy(update={"suggested_rewrite": None})
                    for finding in result.findings
                ]
            }
        )


class StubSynthesisLLM:
    """
    Deterministic stand-in for the synthesis chat completion.

    Applies the first finding's suggested rewrite and marks every finding as
    applied, so the real synthesizer's validation runs without Azure.
    """

    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> str:
        import json

        self.calls.append(messages)
        payload = json.loads(messages[1]["content"])
        findings = payload["findings"]
        text = next(
            (f["suggested_rewrite"] for f in findings if f.get("suggested_rewrite")),
            payload["original_description"],
        )
        return json.dumps(
            {
                "recommended_description": text,
                "summary": "Applied the review findings.",
                "contributions": [
                    {"finding_id": f["finding_id"], "status": "applied", "contribution": "Applied"}
                    for f in findings
                ],
                "skillz_changes": [],
                "conflicts": [],
                "open_items": [],
            }
        )


class ReviewEngineHarness:
    """Installs review-engine stand-ins onto the test app and resets them after."""

    def __init__(self, app) -> None:
        self._app = app
        self.synthesis_llm = StubSynthesisLLM()

    def install(
        self,
        result: ConsolidatedReviewResult
        | Callable[[RequirementReviewInput], ConsolidatedReviewResult],  # type: ignore[name-defined]
    ) -> None:
        """Install an enhancer returning *result* and drop cached review services."""
        self.reset()
        self._app.state.llm_enhancer = StubLLMReviewEnhancer(result)
        self.synthesis_llm = StubSynthesisLLM()
        self._app.state.recommendation_synthesizer = RecommendationSynthesizer(
            self.synthesis_llm, skillz_service=None
        )

    def install_default(self) -> None:
        """Install an engine that completes and returns exactly one finding."""
        self.install(
            ConsolidatedReviewResult(
                findings=[build_stub_finding()],
                completion=ReviewCompletion.complete(),
            )
        )

    def reset(self) -> None:
        """Clear the enhancer and every review service cached against it."""
        for attribute in _CACHED_REVIEW_STATE:
            if hasattr(self._app.state, attribute):
                delattr(self._app.state, attribute)


def _test_settings() -> AppSettings:
    """Override settings for unit tests - avoids needing a real .env file."""
    # Reset the lru_cache so tests get a fresh settings object
    get_settings.cache_clear()
    return AppSettings(
        environment="local",
        debug=True,
        log_level="DEBUG",
        # Minimal Azure stubs - real values not needed for unit tests
        azure_openai={
            "endpoint": "https://test.openai.azure.com",
            "api_key": "test-key",
            "chat_deployment": "gpt-4o-test",
            "embedding_deployment": "embedding-test",
            # Explicit so tests never fall through to a real .env value for
            # these optional fields (BaseSettings still consults env_file for
            # any key omitted here).
            "rag_chat_deployment": None,
            "rag_chat_max_tokens": 1200,
        },
        azure_search={
            "endpoint": "https://test.search.windows.net",
            "api_key": "test-key",
        },
        azure_blob={
            "connection_string": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;",
        },
        sharepoint={
            "tenant_id": "",
            "client_id": "",
            "client_secret": "",
            "site_url": "",
            "drive_name": "Requirements Management",
            "standards_folder": "0. Reference Material/AI Reference Material",
            "cache_ttl_seconds": 300,
        },
        jama={
            "base_url": "",
            "auth_type": "basic",
            "username": "",
            "password": "",
            "client_id": "",
            "client_secret": "",
            "credential_encryption_key": "",
        },
        # Explicit so a developer's .env can never switch tests to real Entra auth.
        entra={"tenant_id": "", "client_id": "", "audience": ""},
        local_dev_user_roles=["Radia.Admin"],
    )


@pytest.fixture(scope="session")
def test_app():
    """Create a test FastAPI application instance."""
    get_settings.cache_clear()
    test_settings = _test_settings()
    app = create_app()
    app.state.settings = test_settings
    app.dependency_overrides[get_settings] = lambda: test_settings
    return app


@pytest.fixture
def test_settings() -> AppSettings:
    """Settings object for tests that construct components directly."""
    return _test_settings()


@pytest.fixture(autouse=True)
def review_engine(test_app) -> ReviewEngineHarness:
    """
    Install a deterministic review engine for every test.

    Autouse so no unit test ever calls Azure OpenAI or Azure AI Search, and so a
    review that is expected to produce findings actually does.
    """
    # Provide an in-memory blob client so ReviewHistoryRepository works in tests
    blob = InMemoryBlobClient()
    test_app.state.blob_client = blob
    test_app.state.review_history_repository = ReviewHistoryRepository(blob)
    # Clear cached history service so it's rebuilt with the fresh repo
    if hasattr(test_app.state, "review_history_service"):
        delattr(test_app.state, "review_history_service")

    harness = ReviewEngineHarness(test_app)
    harness.install_default()
    yield harness
    harness.reset()


@pytest.fixture
def client(test_app) -> TestClient:
    """Synchronous test client for simple endpoint tests."""
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# Microsoft Entra ID test identity provider
# ---------------------------------------------------------------------------

TEST_TENANT_ID = "11111111-1111-1111-1111-111111111111"
TEST_API_CLIENT_ID = "22222222-2222-2222-2222-222222222222"
TEST_SIGNING_KID = "test-signing-key"


class EntraTokenFactory:
    """Mints RS256 access tokens shaped like real Entra ID v1/v2 API tokens."""

    def __init__(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import rsa

        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = TEST_SIGNING_KID
        self.jwks_fetch_count = 0

    def jwks(self) -> dict[str, Any]:
        import json

        import jwt

        self.jwks_fetch_count += 1
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.private_key.public_key()))
        jwk.update({"kid": self.kid, "use": "sig", "alg": "RS256"})
        return {"keys": [jwk]}

    def token(
        self,
        *,
        oid: str = "user-alice",
        email: str = "alice@radia.example",
        name: str = "Alice Engineer",
        roles: list[str] | None = None,
        scp: str | None = "access_as_user",
        version: str = "2.0",
        expires_in: int = 3600,
        signing_key: Any = None,
        kid: str | None = None,
        **overrides: Any,
    ) -> str:
        import time

        import jwt

        now = int(time.time())
        if version == "1.0":
            aud, iss = f"api://{TEST_API_CLIENT_ID}", f"https://sts.windows.net/{TEST_TENANT_ID}/"
        else:
            aud, iss = (
                TEST_API_CLIENT_ID,
                f"https://login.microsoftonline.com/{TEST_TENANT_ID}/v2.0",
            )
        claims: dict[str, Any] = {
            "aud": aud,
            "iss": iss,
            "iat": now,
            "nbf": now,
            "exp": now + expires_in,
            "tid": TEST_TENANT_ID,
            "oid": oid,
            "sub": f"sub-{oid}",
            "name": name,
            "preferred_username": email,
            "ver": version,
            "roles": ["Radia.User"] if roles is None else roles,
        }
        if scp is not None:
            claims["scp"] = scp
        claims.update(overrides)
        claims = {key: value for key, value in claims.items() if value is not None}
        return jwt.encode(
            claims,
            signing_key or self.private_key,
            algorithm="RS256",
            headers={"kid": kid or self.kid},
        )

    def headers(self, **kwargs: Any) -> dict[str, str]:
        return {"Authorization": "Bearer " + self.token(**kwargs)}


@pytest.fixture(scope="session")
def entra_tokens() -> EntraTokenFactory:
    return EntraTokenFactory()


@pytest.fixture
def secured_app(test_app, entra_tokens: EntraTokenFactory):
    """
    Switch the shared test app to real Entra ID token validation for one test.

    Signing keys come from ``entra_tokens`` instead of login.microsoftonline.com;
    everything else (signature, issuer, audience, expiry, tenant, scope, roles)
    is the production code path.
    """
    from app.core.config import EntraIDSettings
    from app.core.security import EntraTokenValidator

    base_settings = _test_settings()
    secured_settings = base_settings.model_copy(
        update={
            "environment": "test",
            "entra": EntraIDSettings(tenant_id=TEST_TENANT_ID, client_id=TEST_API_CLIENT_ID),
        }
    )
    previous_override = test_app.dependency_overrides.get(get_settings)
    previous_settings = getattr(test_app.state, "settings", None)
    test_app.dependency_overrides[get_settings] = lambda: secured_settings
    test_app.state.settings = secured_settings
    test_app.state.entra_token_validator = EntraTokenValidator(
        secured_settings.entra, jwks_fetcher=entra_tokens.jwks
    )
    yield test_app
    if previous_override is not None:
        test_app.dependency_overrides[get_settings] = previous_override
    test_app.state.settings = previous_settings
    delattr(test_app.state, "entra_token_validator")


@pytest.fixture
def secured_client(secured_app) -> TestClient:
    return TestClient(secured_app)


@pytest.fixture
async def async_client(test_app) -> AsyncClient:
    """Async test client for async endpoint and service tests."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        yield client
