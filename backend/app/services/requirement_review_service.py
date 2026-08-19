"""Service for single requirement deterministic reviews."""

from app.models.review_models import RequirementReviewInput, RequirementReviewResponse
from app.reviewers.orchestrator import ReviewOrchestrator


class RequirementReviewService:
    """Executes individual requirement review workflow."""

    def __init__(self, orchestrator: ReviewOrchestrator) -> None:
        self._orchestrator = orchestrator

    def review_requirement(self, payload: RequirementReviewInput) -> RequirementReviewResponse:
        return self._orchestrator.review_requirement(payload)
