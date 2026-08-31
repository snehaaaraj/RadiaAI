"""
Test configuration — shared fixtures and test client setup.

pytest-asyncio is configured in auto mode (see pyproject.toml), so
async test functions work without explicit @pytest.mark.asyncio decorators.

Unit tests never reach Azure. The `review_engine` fixture is autouse and installs
a deterministic stand-in for the consolidated LLM enhancer, so the review pipeline
is exercised end-to-end without network access. Tests that need a specific engine
behaviour (a failure, a per-requirement outcome) call `review_engine.install(...)`.
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.core.config import AppSettings, get_settings
from app.main import create_app
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    ConsolidatedReviewResult,
    FindingSeverity,
    PassFail,
    RequirementReviewInput,
    ReviewCompletion,
    ReviewFinding,
    ReviewStatus,
)

# Services cached on app.state that must be dropped when the engine is swapped,
# so the DI container rebuilds them against the new enhancer.
_CACHED_REVIEW_STATE = (
    "llm_enhancer",
    "review_orchestrator",
    "review_version_service",
    "requirement_review_service",
    "requirement_delta_review_service",
)


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
    cover partially-failed delta runs.
    """

    def __init__(
        self,
        result: ConsolidatedReviewResult
        | Callable[[RequirementReviewInput], ConsolidatedReviewResult],
    ) -> None:
        self._result = result

    def consolidated_review(self, payload: RequirementReviewInput) -> ConsolidatedReviewResult:
        if callable(self._result):
            return self._result(payload)
        return self._result


class ReviewEngineHarness:
    """Installs review-engine stand-ins onto the test app and resets them after."""

    def __init__(self, app) -> None:
        self._app = app

    def install(
        self,
        result: ConsolidatedReviewResult
        | Callable[[RequirementReviewInput], ConsolidatedReviewResult],
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
