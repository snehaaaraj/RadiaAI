"""
Test configuration — shared fixtures and test client setup.

pytest-asyncio is configured in auto mode (see pyproject.toml), so
async test functions work without explicit @pytest.mark.asyncio decorators.

Unit tests never reach Azure. The `review_engine` fixture is autouse and installs
a deterministic stand-in for the consolidated LLM enhancer, so the review pipeline
is exercised end-to-end without network access. Tests that need a specific engine
behaviour (a failure, a per-requirement outcome) call `review_engine.install(...)`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from azure.core.exceptions import ResourceNotFoundError
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

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

if TYPE_CHECKING:
    from collections.abc import Callable

# Services cached on app.state that must be dropped when the engine is swapped,
# so the DI container rebuilds them against the new enhancer.
_CACHED_REVIEW_STATE = (
    "llm_enhancer",
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

    Accepts a callable so a test can vary the result per requirement — needed to
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


class ReviewEngineHarness:
    """Installs review-engine stand-ins onto the test app and resets them after."""

    def __init__(self, app) -> None:
        self._app = app

    def install(
        self,
        result: ConsolidatedReviewResult
        | Callable[[RequirementReviewInput], ConsolidatedReviewResult],  # type: ignore[name-defined]
    ) -> None:
        """Install an enhancer returning *result* and drop cached review services."""
        self.reset()
        self._app.state.llm_enhancer = StubLLMReviewEnhancer(result)

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
    """Override settings for unit tests — avoids needing a real .env file."""
    # Reset the lru_cache so tests get a fresh settings object
    get_settings.cache_clear()
    return AppSettings(
        environment="local",
        debug=True,
        log_level="DEBUG",
        # Minimal Azure stubs — real values not needed for unit tests
        azure_openai={
            "endpoint": "https://test.openai.azure.com",
            "api_key": "test-key",
            "chat_deployment": "gpt-4o-test",
            "embedding_deployment": "embedding-test",
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


@pytest.fixture
async def async_client(test_app) -> AsyncClient:
    """Async test client for async endpoint and service tests."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        yield client
