"""Service for deterministic delta reviews."""

from radia_ai.features.jama_requirement_reviewer.diff.delta_engine import compute_delta
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    DeltaRequirementReviewResult,
    DeltaReviewInput,
    DeltaReviewResponse,
    ReviewStatus,
)
from radia_ai.features.jama_requirement_reviewer.reviewers.orchestrator import ReviewOrchestrator
from radia_ai.features.jama_requirement_reviewer.services.review_version_service import (
    ReviewVersionService,
)
from radia_ai.features.jama_requirement_reviewer.utils.review_scoring import (
    average_score,
    status_from_score,
)
from radia_ai.features.jama_requirement_reviewer.utils.review_utils import (
    aggregate_completions,
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

        overall = self._overall_from_results(reviewed_requirements)
        completion = aggregate_completions([result.completion for result in reviewed_requirements])
        determinism = self._review_version_service.get_review_version().determinism
        return DeltaReviewResponse(
            overall=overall,
            completion=completion,
            change_summary=delta_result.change_summary,
            reviewed_requirements=reviewed_requirements,
            determinism=determinism,
        )

    @staticmethod
    def _overall_from_results(results: list[DeltaRequirementReviewResult]) -> ReviewStatus:
        """
        Roll the changed requirements up into one verdict via their average score.

        A requirement that could not be evaluated contributes no score, so it
        cannot be read as passing; when nothing at all could be evaluated the
        change set is reported as ``NOT_EVALUATED`` rather than acceptable.
        """
        scores = [category.score for result in results for category in result.category_results]
        if results and not scores:
            return ReviewStatus.NOT_EVALUATED
        return status_from_score(average_score(scores))
