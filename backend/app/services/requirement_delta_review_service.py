"""Service for deterministic delta reviews."""

from app.diff.delta_engine import compute_delta
from app.models.review_models import (
    DeltaRequirementReviewResult,
    DeltaReviewInput,
    DeltaReviewResponse,
    RequirementSetReviewInput,
    ReviewStatus,
)
from app.services.requirement_review_service import RequirementReviewService
from app.services.requirement_set_review_service import RequirementSetReviewService
from app.services.review_version_service import ReviewVersionService
from app.utils.review_utils import overall_from_statuses


class RequirementDeltaReviewService:
    """Runs changed-item-only deterministic delta review workflow."""

    def __init__(
        self,
        requirement_review_service: RequirementReviewService,
        requirement_set_review_service: RequirementSetReviewService,
        review_version_service: ReviewVersionService,
    ) -> None:
        self._requirement_review_service = requirement_review_service
        self._requirement_set_review_service = requirement_set_review_service
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
                    category_results=single_result.category_results,
                    findings=single_result.findings,
                )
            )

        set_result = self._requirement_set_review_service.review_requirement_set(
            RequirementSetReviewInput(
                specification_id=payload.specification_id,
                requirements=delta_result.changed_requirements,
                metadata={"mode": "delta"},
            )
        )
        overall = overall_from_statuses(
            [result.overall for result in reviewed_requirements] + [set_result.overall]
        )
        determinism = self._review_version_service.get_review_version().determinism
        return DeltaReviewResponse(
            overall=overall,
            change_summary=delta_result.change_summary,
            reviewed_requirements=reviewed_requirements,
            requirement_set_findings=set_result.findings,
            determinism=determinism,
        )

