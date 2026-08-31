"""
Unit tests for the review completion contract.

The central guarantee under test: a review that did not run is never presented as
a review that found nothing. Every failure mode must surface a FAILED completion
with a specific reason, and an overall status of "Not Evaluated".
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from tests.conftest import build_stub_finding

from app.core.exceptions import LLMError
from app.rag.llm_review_enhancer_v2 import LLMReviewEnhancer
from app.rag.service import RetrievedContext
from radia_ai.features.jama_requirement_reviewer.dependencies.container import get_llm_enhancer
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    ConsolidatedReviewResult,
    RequirementReviewInput,
    ReviewCompletion,
    ReviewCompletionStatus,
    ReviewFailureReason,
    ReviewStatus,
)
from radia_ai.features.jama_requirement_reviewer.reviewers.orchestrator import ReviewOrchestrator
from radia_ai.features.jama_requirement_reviewer.utils.review_utils import (
    aggregate_completions,
    overall_from_statuses,
)

# ---------------------------------------------------------------------------
# Fake RAG service — lets each enhancer stage fail independently
# ---------------------------------------------------------------------------


class FakeRAGService:
    """Stands in for RAGService so each pipeline stage can be failed on demand."""

    def __init__(
        self,
        *,
        chunks: list[dict] | None = None,
        retrieve_error: Exception | None = None,
        generate_error: Exception | None = None,
        response: str = "",
    ) -> None:
        self._chunks = (
            chunks if chunks is not None else [{"filename": "INCOSE-Guide.pdf", "content": "..."}]
        )
        self._retrieve_error = retrieve_error
        self._generate_error = generate_error
        self._response = response

    def retrieve(self, query: str, **_kwargs) -> RetrievedContext:
        if self._retrieve_error is not None:
            raise self._retrieve_error
        return RetrievedContext(chunks=self._chunks, query=query)

    def generate_with_context(self, **_kwargs) -> str:
        if self._generate_error is not None:
            raise self._generate_error
        return self._response


def _payload() -> RequirementReviewInput:
    return RequirementReviewInput(
        requirement_id="REQ-1",
        text="The subsystem should respond fast.",
        requirement_level="system",
    )


# ---------------------------------------------------------------------------
# Enhancer failure modes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_retrieval_failure_is_reported_as_retrieval_failed() -> None:
    enhancer = LLMReviewEnhancer(FakeRAGService(retrieve_error=RuntimeError("search down")))

    result = enhancer.consolidated_review(_payload())

    assert result.completion.status is ReviewCompletionStatus.FAILED
    assert result.completion.reason is ReviewFailureReason.RETRIEVAL_FAILED
    assert result.completion.message
    assert result.findings == []


@pytest.mark.unit
def test_empty_retrieval_is_reported_as_no_standards_context() -> None:
    enhancer = LLMReviewEnhancer(FakeRAGService(chunks=[]))

    result = enhancer.consolidated_review(_payload())

    assert result.completion.status is ReviewCompletionStatus.FAILED
    assert result.completion.reason is ReviewFailureReason.NO_STANDARDS_CONTEXT


@pytest.mark.unit
def test_llm_error_is_reported_as_llm_call_failed() -> None:
    enhancer = LLMReviewEnhancer(
        FakeRAGService(generate_error=LLMError(message="boom", model="gpt-5"))
    )

    result = enhancer.consolidated_review(_payload())

    assert result.completion.status is ReviewCompletionStatus.FAILED
    assert result.completion.reason is ReviewFailureReason.LLM_CALL_FAILED


@pytest.mark.unit
@pytest.mark.parametrize(
    "response",
    [
        "not json at all",
        "",
        '{"findings": "should have been a list"}',
        "[1, 2, 3]",
    ],
)
def test_unusable_llm_response_is_reported_as_invalid(response: str) -> None:
    enhancer = LLMReviewEnhancer(FakeRAGService(response=response))

    result = enhancer.consolidated_review(_payload())

    assert result.completion.status is ReviewCompletionStatus.FAILED
    assert result.completion.reason is ReviewFailureReason.INVALID_LLM_RESPONSE
    assert result.findings == []


@pytest.mark.unit
def test_valid_llm_response_completes_and_returns_findings() -> None:
    response = """```json
    {"findings": [{
        "category": "Ambiguous Wording",
        "reviewer": "language",
        "severity": "Medium",
        "rule": "Avoid subjective terms.",
        "explanation": "'fast' is not measurable.",
        "evidence": "respond fast",
        "recommendation": "Quantify the response time.",
        "reference": "INCOSE-Guide.pdf",
        "suggested_rewrite": "The subsystem shall respond within 100 ms."
    }]}
    ```"""
    enhancer = LLMReviewEnhancer(FakeRAGService(response=response))

    result = enhancer.consolidated_review(_payload())

    assert result.completion.status is ReviewCompletionStatus.COMPLETE
    assert result.completion.reason is None
    assert len(result.findings) == 1
    assert result.findings[0].reviewer == "language"


@pytest.mark.unit
def test_empty_findings_list_is_a_clean_review_not_a_failure() -> None:
    """The distinction this whole contract exists for."""
    enhancer = LLMReviewEnhancer(FakeRAGService(response='{"findings": []}'))

    result = enhancer.consolidated_review(_payload())

    assert result.completion.status is ReviewCompletionStatus.COMPLETE
    assert result.findings == []


# ---------------------------------------------------------------------------
# Orchestrator behaviour
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_orchestrator_without_enhancer_reports_engine_unavailable(test_settings) -> None:
    orchestrator = ReviewOrchestrator(settings=test_settings, reviewers=[], llm_enhancer=None)

    response = orchestrator.review_requirement(_payload())

    assert response.completion.status is ReviewCompletionStatus.FAILED
    assert response.completion.reason is ReviewFailureReason.REVIEW_ENGINE_UNAVAILABLE
    assert response.overall is ReviewStatus.NOT_EVALUATED
    assert response.findings == []
    assert response.category_results == []


@pytest.mark.unit
def test_orchestrator_maps_failed_review_to_not_evaluated(test_settings) -> None:
    class FailingEnhancer:
        def consolidated_review(self, _payload) -> ConsolidatedReviewResult:
            return ConsolidatedReviewResult(
                completion=ReviewCompletion.failed(ReviewFailureReason.NO_STANDARDS_CONTEXT)
            )

    orchestrator = ReviewOrchestrator(
        settings=test_settings, reviewers=[], llm_enhancer=FailingEnhancer()
    )

    response = orchestrator.review_requirement(_payload())

    assert response.overall is ReviewStatus.NOT_EVALUATED
    assert response.completion.reason is ReviewFailureReason.NO_STANDARDS_CONTEXT


@pytest.mark.unit
def test_orchestrator_clean_review_is_acceptable(test_settings) -> None:
    class CleanEnhancer:
        def consolidated_review(self, _payload) -> ConsolidatedReviewResult:
            return ConsolidatedReviewResult(findings=[], completion=ReviewCompletion.complete())

    orchestrator = ReviewOrchestrator(
        settings=test_settings, reviewers=[], llm_enhancer=CleanEnhancer()
    )

    response = orchestrator.review_requirement(_payload())

    assert response.overall is ReviewStatus.ACCEPTABLE
    assert response.completion.status is ReviewCompletionStatus.COMPLETE


# ---------------------------------------------------------------------------
# Dependency wiring
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_di_rebuilds_enhancer_when_app_state_is_empty(test_app, review_engine) -> None:
    """
    A process that never ran lifespan must still get a real review engine.

    Previously the DI fallback built the orchestrator with llm_enhancer=None, so
    every review in such a process silently returned zero findings.
    """
    # Simulate a cold start: nothing cached on app.state.
    review_engine.reset()
    for attribute in ("rag_service", "openai_client", "search_service"):
        if hasattr(test_app.state, attribute):
            delattr(test_app.state, attribute)

    enhancer = get_llm_enhancer(SimpleNamespace(app=test_app))

    assert isinstance(enhancer, LLMReviewEnhancer)
    # Rebuilt dependencies are cached so the next request does not redo the work.
    assert test_app.state.llm_enhancer is enhancer
    assert test_app.state.rag_service is not None


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_requirement_review_endpoint_exposes_failed_completion(
    client: TestClient, review_engine
) -> None:
    review_engine.install(
        ConsolidatedReviewResult(
            completion=ReviewCompletion.failed(ReviewFailureReason.NO_STANDARDS_CONTEXT)
        )
    )

    response = client.post(
        "/api/v1/review/requirement",
        json={"text": "The subsystem should respond fast."},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["overall"] == "Not Evaluated"
    assert data["completion"]["status"] == "failed"
    assert data["completion"]["reason"] == "no_standards_context"
    assert data["completion"]["message"]
    assert data["findings"] == []


@pytest.mark.unit
def test_requirement_review_endpoint_reports_complete_review(client: TestClient) -> None:
    response = client.post(
        "/api/v1/review/requirement",
        json={"text": "The subsystem should respond fast."},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["completion"]["status"] == "complete"
    assert data["completion"]["reason"] is None
    assert len(data["findings"]) >= 1


@pytest.mark.unit
def test_failed_review_is_recorded_in_history_with_its_reason(
    client: TestClient, review_engine
) -> None:
    review_engine.install(
        ConsolidatedReviewResult(
            completion=ReviewCompletion.failed(ReviewFailureReason.LLM_CALL_FAILED)
        )
    )

    client.post(
        "/api/v1/review/requirement",
        json={"requirement_id": "REQ-FAILED", "text": "The subsystem shall respond."},
    )

    entries = client.get("/api/v1/review/history").json()["data"]["entries"]
    latest = entries[0]
    assert latest["completion"]["status"] == "failed"
    assert latest["completion"]["reason"] == "llm_call_failed"
    assert latest["overall"] == "Not Evaluated"


@pytest.mark.unit
def test_delta_review_reports_partial_completion(client: TestClient, review_engine) -> None:
    """One requirement evaluated, one not — the run must not claim to be complete."""

    def per_requirement(payload: RequirementReviewInput) -> ConsolidatedReviewResult:
        if payload.requirement_id == "REQ-001":
            return ConsolidatedReviewResult(
                findings=[build_stub_finding()], completion=ReviewCompletion.complete()
            )
        return ConsolidatedReviewResult(
            completion=ReviewCompletion.failed(ReviewFailureReason.LLM_CALL_FAILED)
        )

    review_engine.install(per_requirement)

    response = client.post(
        "/api/v1/review/delta",
        json={
            "specification_id": "SPEC-1",
            "baseline_requirements": [
                {"requirement_id": "REQ-001", "text": "The system shall respond in 2 s."}
            ],
            "updated_requirements": [
                {"requirement_id": "REQ-001", "text": "The system shall respond in 1 s."},
                {"requirement_id": "REQ-002", "text": "The system shall log faults."},
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["completion"]["status"] == "partial"
    assert "1 of 2" in data["completion"]["message"]

    by_id = {item["requirement_id"]: item for item in data["reviewed_requirements"]}
    assert by_id["REQ-001"]["completion"]["status"] == "complete"
    assert by_id["REQ-002"]["completion"]["status"] == "failed"
    assert by_id["REQ-002"]["overall"] == "Not Evaluated"


@pytest.mark.unit
def test_delta_review_reports_full_failure(client: TestClient, review_engine) -> None:
    review_engine.install(
        ConsolidatedReviewResult(
            completion=ReviewCompletion.failed(ReviewFailureReason.RETRIEVAL_FAILED)
        )
    )

    response = client.post(
        "/api/v1/review/delta",
        json={
            "baseline_requirements": [],
            "updated_requirements": [
                {"requirement_id": "REQ-100", "text": "The system shall log faults."}
            ],
        },
    )

    data = response.json()["data"]
    assert data["completion"]["status"] == "failed"
    assert data["completion"]["reason"] == "retrieval_failed"
    assert data["overall"] == "Not Evaluated"


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_all_not_evaluated_does_not_aggregate_to_acceptable() -> None:
    statuses = [ReviewStatus.NOT_EVALUATED, ReviewStatus.NOT_EVALUATED]
    assert overall_from_statuses(statuses) is ReviewStatus.NOT_EVALUATED


@pytest.mark.unit
def test_real_verdicts_win_over_not_evaluated() -> None:
    statuses = [ReviewStatus.NOT_EVALUATED, ReviewStatus.UNACCEPTABLE]
    assert overall_from_statuses(statuses) is ReviewStatus.UNACCEPTABLE


@pytest.mark.unit
def test_empty_status_list_is_acceptable() -> None:
    assert overall_from_statuses([]) is ReviewStatus.ACCEPTABLE


@pytest.mark.unit
def test_aggregate_completions_handles_each_shape() -> None:
    complete = ReviewCompletion.complete()
    failed = ReviewCompletion.failed(ReviewFailureReason.LLM_CALL_FAILED)

    assert aggregate_completions([]).status is ReviewCompletionStatus.COMPLETE
    assert aggregate_completions([complete, complete]).status is ReviewCompletionStatus.COMPLETE
    assert aggregate_completions([failed, failed]).status is ReviewCompletionStatus.FAILED
    assert aggregate_completions([complete, failed]).status is ReviewCompletionStatus.PARTIAL


@pytest.mark.unit
def test_full_failure_aggregation_keeps_the_cause() -> None:
    failed = ReviewCompletion.failed(ReviewFailureReason.NO_STANDARDS_CONTEXT)

    aggregated = aggregate_completions([failed, failed])

    assert aggregated.reason is ReviewFailureReason.NO_STANDARDS_CONTEXT
    assert aggregated.message == failed.message
