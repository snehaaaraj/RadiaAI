"""
Unit tests for the delta (verification) review contract.

Delta review scores a requirement that a previous review already caused to be
revised. It must therefore: compare against the baseline version, and never hand
back replacement text — the reviewer is checking the revision, not asking for
another one.
"""

import pytest

from app.prompts.review_prompts import CONSOLIDATED_REVIEW_SYSTEM, DELTA_REVIEW_SYSTEM
from app.rag.llm_review_enhancer_v2 import LLMReviewEnhancer
from radia_ai.features.jama_requirement_reviewer.diff.delta_engine import compute_delta
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    RequirementReviewInput,
)


class RecordingRAGService:
    """Captures the prompt and user message handed to the model."""

    def __init__(self, response: str = '{"findings": []}') -> None:
        self._response = response
        self.system_prompt: str | None = None
        self.user_message: str | None = None

    def retrieve(self, *_args, **_kwargs):
        from app.rag.service import RetrievedContext

        return RetrievedContext(chunks=[{"filename": "INCOSE-Guide.pdf", "content": "..."}])

    def generate_with_context(self, system_prompt: str, user_message: str, context) -> str:
        self.system_prompt = system_prompt
        self.user_message = user_message
        return self._response


def _revision(baseline_text: str, updated_text: str):
    result = compute_delta(
        baseline_requirements=[
            RequirementReviewInput(requirement_id="REQ-001", text=baseline_text)
        ],
        updated_requirements=[RequirementReviewInput(requirement_id="REQ-001", text=updated_text)],
    )
    return result.changed_revisions[0]


# ---------------------------------------------------------------------------
# Baseline is carried into the scoring call
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_modified_requirement_carries_its_baseline_text() -> None:
    revision = _revision("The system shall be fast.", "The system shall respond within 100 ms.")

    # Both sides go through the same normalization, so compare on content.
    assert "The system shall be fast." in (revision.baseline_text or "")
    assert "The system shall respond within 100 ms." in revision.requirement.text


@pytest.mark.unit
def test_new_requirement_has_no_baseline_text() -> None:
    result = compute_delta(
        baseline_requirements=[],
        updated_requirements=[RequirementReviewInput(requirement_id="REQ-NEW", text="New text.")],
    )

    assert result.changed_revisions[0].baseline_text is None


@pytest.mark.unit
def test_scoring_call_shows_the_model_both_versions() -> None:
    rag = RecordingRAGService()
    enhancer = LLMReviewEnhancer(rag)

    enhancer.score_revision(_revision("The system shall be fast.", "The system shall be quick."))

    assert rag.system_prompt == DELTA_REVIEW_SYSTEM
    assert "The system shall be fast." in (rag.user_message or "")
    assert "The system shall be quick." in (rag.user_message or "")


@pytest.mark.unit
def test_authoring_review_still_uses_the_consolidated_prompt() -> None:
    rag = RecordingRAGService()
    enhancer = LLMReviewEnhancer(rag)

    enhancer.consolidated_review(RequirementReviewInput(text="The system shall be fast."))

    assert rag.system_prompt == CONSOLIDATED_REVIEW_SYSTEM


# ---------------------------------------------------------------------------
# Pairing requirements that carry no ID
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pasted_revision_without_an_id_is_a_modification_not_an_add_and_delete() -> None:
    """
    The core delta workflow: paste the original, paste the revision.

    Keying an unidentified requirement by its text made this impossible — the
    revision's text differs, so it never matched its baseline and was reported as
    one deletion plus one addition, scored with no previous version.
    """
    result = compute_delta(
        baseline_requirements=[RequirementReviewInput(text="The system should be fast.")],
        updated_requirements=[
            RequirementReviewInput(text="The system shall respond within 100 ms.")
        ],
    )

    assert result.change_summary.modified_requirement_ids == ["Requirement 1"]
    assert result.change_summary.new_requirement_ids == []
    assert result.change_summary.deleted_requirement_ids == []

    revision = result.changed_revisions[0]
    assert "The system should be fast." in (revision.baseline_text or "")


@pytest.mark.unit
def test_unidentified_requirements_get_a_readable_label() -> None:
    """A result labelled '<missing-id>' told the reviewer nothing."""
    result = compute_delta(
        baseline_requirements=[
            RequirementReviewInput(text="First original."),
            RequirementReviewInput(text="Second original."),
        ],
        updated_requirements=[
            RequirementReviewInput(text="First revised."),
            RequirementReviewInput(text="Second revised."),
        ],
    )

    assert [revision.key for revision in result.changed_revisions] == [
        "Requirement 1",
        "Requirement 2",
    ]


@pytest.mark.unit
def test_unidentified_requirements_pair_by_position() -> None:
    result = compute_delta(
        baseline_requirements=[
            RequirementReviewInput(text="First original."),
            RequirementReviewInput(text="Second original."),
        ],
        updated_requirements=[
            RequirementReviewInput(text="First revised."),
            RequirementReviewInput(text="Second original."),
        ],
    )

    # Only the first position changed; the second is untouched at its position.
    assert result.change_summary.modified_requirement_ids == ["Requirement 1"]
    assert [revision.key for revision in result.changed_revisions] == ["Requirement 1"]
    assert "First original." in (result.changed_revisions[0].baseline_text or "")


@pytest.mark.unit
def test_explicit_ids_still_win_over_position() -> None:
    """Reordered requirements with IDs must pair by ID, not by position."""
    result = compute_delta(
        baseline_requirements=[
            RequirementReviewInput(requirement_id="REQ-A", text="Alpha original."),
            RequirementReviewInput(requirement_id="REQ-B", text="Bravo original."),
        ],
        updated_requirements=[
            RequirementReviewInput(requirement_id="REQ-B", text="Bravo original."),
            RequirementReviewInput(requirement_id="REQ-A", text="Alpha revised."),
        ],
    )

    assert result.change_summary.modified_requirement_ids == ["REQ-A"]
    assert [revision.key for revision in result.changed_revisions] == ["REQ-A"]
    assert "Alpha original." in (result.changed_revisions[0].baseline_text or "")


@pytest.mark.unit
def test_extra_updated_requirement_without_an_id_is_new() -> None:
    result = compute_delta(
        baseline_requirements=[RequirementReviewInput(text="Only original.")],
        updated_requirements=[
            RequirementReviewInput(text="Only revised."),
            RequirementReviewInput(text="Brand new requirement."),
        ],
    )

    assert result.change_summary.modified_requirement_ids == ["Requirement 1"]
    assert result.change_summary.new_requirement_ids == ["Requirement 2"]
    keyed = {revision.key: revision for revision in result.changed_revisions}
    assert keyed["Requirement 2"].baseline_text is None


@pytest.mark.unit
def test_delta_endpoint_labels_unidentified_requirements(client) -> None:
    response = client.post(
        "/api/v1/review/delta",
        json={
            "baseline_requirements": [{"text": "The system should be fast."}],
            "updated_requirements": [{"text": "The system shall respond within 100 ms."}],
        },
    )
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["change_summary"]["modified_requirement_ids"] == ["Requirement 1"]
    reviewed_ids = [item["requirement_id"] for item in data["reviewed_requirements"]]
    assert reviewed_ids == ["Requirement 1"]
    assert "<missing-id>" not in reviewed_ids


# ---------------------------------------------------------------------------
# No rewrites are proposed
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_delta_prompt_forbids_suggested_rewrites() -> None:
    assert (
        "suggested_rewrite"
        not in DELTA_REVIEW_SYSTEM.split("Never include")[0].split('"findings"')[1]
    )
    assert 'Never include a "suggested_rewrite" field' in DELTA_REVIEW_SYSTEM


@pytest.mark.unit
def test_scoring_strips_a_rewrite_even_if_the_model_returns_one() -> None:
    """The contract is enforced in code, not left to prompt compliance."""
    rag = RecordingRAGService(
        response="""{"findings": [{
            "category": "Ambiguous Wording",
            "reviewer": "language",
            "severity": "Medium",
            "rule": "Requirements shall be unambiguous.",
            "explanation": "'quick' is not measurable.",
            "evidence": "quick",
            "recommendation": "Quantify the response time.",
            "reference": "INCOSE-Guide.pdf",
            "suggested_rewrite": "The system shall respond within 100 ms."
        }]}"""
    )
    enhancer = LLMReviewEnhancer(rag)

    result = enhancer.score_revision(
        _revision("The system shall be fast.", "The system shall be quick.")
    )

    assert len(result.findings) == 1
    assert result.findings[0].suggested_rewrite is None
    # The reason the finding was raised is still reported.
    assert result.findings[0].recommendation == "Quantify the response time."


@pytest.mark.unit
def test_authoring_review_keeps_the_rewrite() -> None:
    rag = RecordingRAGService(
        response="""{"findings": [{
            "category": "Ambiguous Wording",
            "reviewer": "language",
            "severity": "Medium",
            "rule": "Requirements shall be unambiguous.",
            "explanation": "'quick' is not measurable.",
            "evidence": "quick",
            "recommendation": "Quantify the response time.",
            "reference": "INCOSE-Guide.pdf",
            "suggested_rewrite": "The system shall respond within 100 ms."
        }]}"""
    )
    enhancer = LLMReviewEnhancer(rag)

    result = enhancer.consolidated_review(RequirementReviewInput(text="The system shall be quick."))

    assert result.findings[0].suggested_rewrite == "The system shall respond within 100 ms."


@pytest.mark.unit
def test_delta_endpoint_returns_no_suggested_rewrites(client) -> None:
    """End-to-end: the delta response must not carry replacement text."""
    response = client.post(
        "/api/v1/review/delta",
        json={
            "specification_id": "SPEC-1",
            "baseline_requirements": [
                {"requirement_id": "REQ-001", "text": "The system shall be fast."}
            ],
            "updated_requirements": [
                {"requirement_id": "REQ-001", "text": "The system shall respond within 100 ms."}
            ],
        },
    )
    assert response.status_code == 200

    reviewed = response.json()["data"]["reviewed_requirements"]
    assert reviewed, "expected the modified requirement to be scored"
    for requirement in reviewed:
        for finding in requirement["findings"]:
            assert finding["suggested_rewrite"] is None
