"""Service exposing review engine version metadata."""

from radia_ai.features.jama_requirement_reviewer.models.review_models import ReviewVersionResponse
from radia_ai.features.jama_requirement_reviewer.reviewers.orchestrator import ReviewOrchestrator


class ReviewVersionService:
    """Thin service wrapper around review orchestrator version metadata."""

    def __init__(self, orchestrator: ReviewOrchestrator) -> None:
        self._orchestrator = orchestrator

    def get_review_version(self) -> ReviewVersionResponse:
        return self._orchestrator.build_version_response()


