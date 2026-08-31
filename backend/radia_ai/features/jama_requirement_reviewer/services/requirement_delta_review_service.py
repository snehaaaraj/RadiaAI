"""Service for deterministic delta reviews."""

from radia_ai.features.jama_requirement_reviewer.diff.delta_engine import compute_delta
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    DeltaRequirementReviewResult,
    DeltaReviewInput,
    DeltaReviewResponse,
)
from radia_ai.features.jama_requirement_reviewer.services.requirement_review_service import (
    RequirementReviewService,
)
from radia_ai.features.jama_requirement_reviewer.services.review_version_service import (
    ReviewVersionService,
)
from radia_ai.features.jama_requirement_reviewer.utils.review_utils import (
    aggregate_completions,
    overall_from_statuses,
)


class RequirementDeltaReviewService:
    """Runs changed-item-only delta review workflow."""

    def __init__(
        self,
        requirement_review_service: RequirementReviewService,
        review_version_service: ReviewVersionService,
    ) -> None:
        self._requirement_review_service = requirement_review_service
        self._review_version_service = review_version_service

    def review_delta(self, payload: DeltaReviewInput) -> DeltaReviewResponse:
        delta_result = compute_delta(
            baseline_requirements=payload.baseline_requirements,
            updated_requirements=payload.updated_requirements,
            changed_trace_links=payload.changed_trace_links,
        )

        reviewed_requirements = []
        for requirement in delta_result.changed_requirements:
            single_result = self._requirement_review_service.review_requirement(requirement)
            reviewed_requirements.append(
                DeltaRequirementReviewResult(
                    requirement_id=requirement.requirement_id or "<missing-id>",
                    overall=single_result.overall,
                    completion=single_result.completion,
                    category_results=single_result.category_results,
                    findings=single_result.findings,
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
