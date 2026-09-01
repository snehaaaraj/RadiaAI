"""Service for deterministic delta reviews."""

from radia_ai.features.jama_requirement_reviewer.diff.delta_engine import compute_delta
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    DeltaRequirementReviewResult,
    DeltaReviewInput,
    DeltaReviewResponse,
)
from radia_ai.features.jama_requirement_reviewer.reviewers.orchestrator import ReviewOrchestrator
from radia_ai.features.jama_requirement_reviewer.services.review_version_service import (
    ReviewVersionService,
)
from radia_ai.features.jama_requirement_reviewer.utils.review_utils import (
    aggregate_completions,
    overall_from_statuses,
)


class RequirementDeltaReviewService:
    """
    Runs the changed-item-only delta review workflow.

    Delta review *verifies* revisions rather than authoring them: each changed
    requirement is scored against its baseline and the standards library, and no
    replacement text is proposed.
    """

    def __init__(
        self,
        orchestrator: ReviewOrchestrator,
        review_version_service: ReviewVersionService,
    ) -> None:
        self._orchestrator = orchestrator
        self._review_version_service = review_version_service

    def review_delta(self, payload: DeltaReviewInput) -> DeltaReviewResponse:
        delta_result = compute_delta(
            baseline_requirements=payload.baseline_requirements,
            updated_requirements=payload.updated_requirements,
        )

        reviewed_requirements = []
        for revision in delta_result.changed_revisions:
            scored = self._orchestrator.score_revision(revision)
            reviewed_requirements.append(
                DeltaRequirementReviewResult(
                    requirement_id=revision.key,
                    overall=scored.overall,
                    completion=scored.completion,
                    category_results=scored.category_results,
                    findings=scored.findings,
                )
            )

        overall = overall_from_statuses([result.overall for result in reviewed_requirements])
        completion = aggregate_completions([result.completion for result in reviewed_requirements])
        determinism = self._review_version_service.get_review_version().determinism
        return DeltaReviewResponse(
            overall=overall,
            completion=completion,
            change_summary=delta_result.change_summary,
            reviewed_requirements=reviewed_requirements,
            determinism=determinism,
        )
