"""Service for deterministic requirement-set reviews."""

from app.models.review_models import RequirementSetReviewInput, RequirementSetReviewResponse
from app.reviewers.orchestrator import ReviewOrchestrator


class RequirementSetReviewService:
    """Executes requirement-set review workflow."""

    def __init__(self, orchestrator: ReviewOrchestrator) -> None:
        self._orchestrator = orchestrator

    def review_requirement_set(
        self, payload: RequirementSetReviewInput
    ) -> RequirementSetReviewResponse:
        return self._orchestrator.review_requirement_set(payload)
