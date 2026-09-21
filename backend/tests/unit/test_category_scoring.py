"""
Unit tests for the category scoring contract.

The guarantee under test: a completed review scores *every* category. A category
that produced no findings is reported as Acceptable, never omitted - an omitted
category is indistinguishable from one that was never evaluated. Traceability is
out of scope and must not appear anywhere in the pipeline.
"""

import pytest
from tests.conftest import build_stub_finding

from app.prompts.review_prompts import CONSOLIDATED_REVIEW_SYSTEM
from app.rag.llm_review_enhancer_v2 import _VALID_REVIEWERS
from radia_ai.features.jama_requirement_reviewer.models.review_history_models import (
    create_delta_history_entry,
)
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    REVIEW_CATEGORIES,
    ConsolidatedReviewResult,
    DeltaReviewResponse,
    FindingSeverity,
    RequirementReviewInput,
    ReviewCategory,
    ReviewCompletion,
    ReviewStatus,
)
from radia_ai.features.jama_requirement_reviewer.reviewers.consolidated import (
    build_category_reviewers,
)
from radia_ai.features.jama_requirement_reviewer.reviewers.orchestrator import ReviewOrchestrator

SCORED_CATEGORIES = {category.value for category in REVIEW_CATEGORIES}


def _payload() -> RequirementReviewInput:
    return RequirementReviewInput(text="The subsystem should respond fast.")


class _StaticEnhancer:
    """Returns a fixed set of findings so category rollup can be asserted."""

    def __init__(self, findings) -> None:
        self._findings = findings

    def consolidated_review(self, _payload) -> ConsolidatedReviewResult:
        return ConsolidatedReviewResult(
            findings=self._findings, completion=ReviewCompletion.complete()
        )


def _review(test_settings, findings):
    orchestrator = ReviewOrchestrator(
        settings=test_settings, reviewers=[], llm_enhancer=_StaticEnhancer(findings)
    )
    return orchestrator.review_requirement(_payload())


# ---------------------------------------------------------------------------
# Every category is scored
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_clean_review_scores_every_category_as_acceptable(test_settings) -> None:
    response = _review(test_settings, [])

    scored = {result.category: result.status for result in response.category_results}
    assert scored == dict.fromkeys(SCORED_CATEGORIES, ReviewStatus.ACCEPTABLE)


@pytest.mark.unit
def test_category_without_findings_is_acceptable_not_unevaluated(test_settings) -> None:
    """The bug this test pins: a clean category used to be omitted entirely."""
    response = _review(
        test_settings,
        [build_stub_finding(reviewer=ReviewCategory.LANGUAGE.value)],
    )

    scored = {result.category: result.status for result in response.category_results}
    assert set(scored) == SCORED_CATEGORIES
    assert scored[ReviewCategory.LANGUAGE.value] is ReviewStatus.REVISION_RECOMMENDED
    for clean in SCORED_CATEGORIES - {ReviewCategory.LANGUAGE.value}:
        assert scored[clean] is ReviewStatus.ACCEPTABLE
        assert scored[clean] is not ReviewStatus.NOT_EVALUATED


@pytest.mark.unit
def test_category_score_reflects_worst_finding_in_that_category(test_settings) -> None:
    response = _review(
        test_settings,
        [
            build_stub_finding(
                reviewer=ReviewCategory.STRUCTURE.value,
                status=ReviewStatus.REVISION_RECOMMENDED,
            ),
            build_stub_finding(
                reviewer=ReviewCategory.STRUCTURE.value,
                severity=FindingSeverity.CRITICAL,
                status=ReviewStatus.UNACCEPTABLE,
            ),
        ],
    )

    scored = {result.category: result for result in response.category_results}
    structure = scored[ReviewCategory.STRUCTURE.value]
    # Critical costs 8.0, the extra Medium costs half of 4.0 -> 10 - 10 = 0.
    assert structure.score == 0.0
    assert structure.status is ReviewStatus.UNACCEPTABLE
    # The other three categories are clean, so the average still allows revision
    # rather than condemning the whole requirement over one category.
    assert response.overall is ReviewStatus.REVISION_RECOMMENDED


@pytest.mark.unit
def test_a_clean_category_scores_a_full_ten(test_settings) -> None:
    """A well-written requirement is not capped below a perfect score."""
    response = _review(test_settings, [])

    assert [result.score for result in response.category_results] == [10.0] * len(SCORED_CATEGORIES)
    assert response.overall is ReviewStatus.ACCEPTABLE


@pytest.mark.unit
def test_category_score_varies_with_severity_not_just_status(test_settings) -> None:
    """Scores are earned from findings, never looked up from the category or status."""
    low = _review(
        test_settings,
        [build_stub_finding(reviewer=ReviewCategory.LANGUAGE.value, severity=FindingSeverity.LOW)],
    )
    high = _review(
        test_settings,
        [build_stub_finding(reviewer=ReviewCategory.LANGUAGE.value, severity=FindingSeverity.HIGH)],
    )

    low_score = next(
        r.score for r in low.category_results if r.category == ReviewCategory.LANGUAGE.value
    )
    high_score = next(
        r.score for r in high.category_results if r.category == ReviewCategory.LANGUAGE.value
    )
    assert low_score > high_score
    assert low_score < 10.0


@pytest.mark.unit
def test_one_weak_category_does_not_force_an_unacceptable_overall(test_settings) -> None:
    """The regression this pins: a single bad sub-category condemned the whole review."""
    response = _review(
        test_settings,
        [
            build_stub_finding(
                reviewer=ReviewCategory.CERTIFICATION.value,
                severity=FindingSeverity.CRITICAL,
                status=ReviewStatus.UNACCEPTABLE,
            )
        ],
    )

    scored = {result.category: result for result in response.category_results}
    assert scored[ReviewCategory.CERTIFICATION.value].status is ReviewStatus.UNACCEPTABLE
    # (10 + 10 + 10 + 2) / 4 = 8.0 -> Acceptable on average.
    assert response.overall is ReviewStatus.ACCEPTABLE


@pytest.mark.unit
def test_categories_are_returned_in_presentation_order(test_settings) -> None:
    response = _review(test_settings, [])

    assert [result.category for result in response.category_results] == [
        category.value for category in REVIEW_CATEGORIES
    ]


@pytest.mark.unit
def test_finding_from_an_unexpected_category_is_still_scored(test_settings) -> None:
    """An off-contract reviewer value must not silently drop the finding."""
    response = _review(
        test_settings,
        [
            build_stub_finding(
                reviewer="something-unexpected",
                severity=FindingSeverity.CRITICAL,
                status=ReviewStatus.UNACCEPTABLE,
            )
        ],
    )

    scored = {result.category: result for result in response.category_results}
    assert scored["something-unexpected"].status is ReviewStatus.UNACCEPTABLE
    assert scored["something-unexpected"].score < 5.0


@pytest.mark.unit
def test_failed_review_reports_no_category_scores(test_settings) -> None:
    """A review that never ran has nothing to score - not even an Acceptable."""
    orchestrator = ReviewOrchestrator(settings=test_settings, reviewers=[], llm_enhancer=None)

    response = orchestrator.review_requirement(_payload())

    assert response.category_results == []
    assert response.overall is ReviewStatus.NOT_EVALUATED


# ---------------------------------------------------------------------------
# Traceability is out of scope
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_scored_categories_exclude_traceability() -> None:
    assert {"language", "structure", "verifiability", "certification"} == SCORED_CATEGORIES


@pytest.mark.unit
def test_prompt_does_not_ask_for_traceability_findings() -> None:
    assert "**Traceability**" not in CONSOLIDATED_REVIEW_SYSTEM
    for category in REVIEW_CATEGORIES:
        assert f"**{category.value.capitalize()}**" in CONSOLIDATED_REVIEW_SYSTEM


@pytest.mark.unit
def test_response_parser_rejects_traceability_as_a_reviewer() -> None:
    assert "traceability" not in _VALID_REVIEWERS
    assert _VALID_REVIEWERS == SCORED_CATEGORIES


@pytest.mark.unit
def test_version_metadata_is_published_for_every_scored_category() -> None:
    assert [reviewer.name for reviewer in build_category_reviewers()] == [
        category.value for category in REVIEW_CATEGORIES
    ]


# ---------------------------------------------------------------------------
# Delta history rollup
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_delta_history_reports_each_category_once(client) -> None:
    """Concatenating per-requirement categories would repeat each one per item."""
    response = client.post(
        "/api/v1/review/delta",
        json={
            "specification_id": "SPEC-1",
            "baseline_requirements": [{"requirement_id": "REQ-001", "text": "Old text here."}],
            "updated_requirements": [
                {"requirement_id": "REQ-001", "text": "New text here."},
                {"requirement_id": "REQ-002", "text": "Another new requirement."},
            ],
        },
    )
    assert response.status_code == 200

    delta = DeltaReviewResponse.model_validate(response.json()["data"])
    assert len(delta.reviewed_requirements) == 2

    entry = create_delta_history_entry(
        review_id="rev-1", created_at="2026-01-01T00:00:00Z", subject_id="SPEC-1", response=delta
    )

    categories = [result.category for result in entry.category_results]
    assert sorted(categories) == sorted(SCORED_CATEGORIES)
