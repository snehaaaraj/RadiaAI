"""Verifiability reviewer (skeleton)."""

from app.models.review_models import (
    RequirementReviewInput,
    RequirementSetReviewInput,
    ReviewerResult,
    ReviewStatus,
)
from app.reviewers.base import RequirementReviewer


class VerifiabilityReviewer(RequirementReviewer):
    name = "verifiability"
    reviewer_version = "1.0.0"
    prompt_version = "verifiability.v1"
    standards_version = "incose.v1"
    supports_individual_review = True
    supports_requirement_set_review = False

    def review_requirement(self, payload: RequirementReviewInput) -> ReviewerResult:
        return ReviewerResult(
            reviewer=self.name,
            reviewer_version=self.reviewer_version,
            prompt_version=self.prompt_version,
            standards_version=self.standards_version,
            overall=ReviewStatus.ACCEPTABLE,
            findings=[],
        )

    def review_requirement_set(self, payload: RequirementSetReviewInput) -> ReviewerResult:
        return ReviewerResult(
            reviewer=self.name,
            reviewer_version=self.reviewer_version,
            prompt_version=self.prompt_version,
            standards_version=self.standards_version,
            overall=ReviewStatus.ACCEPTABLE,
            findings=[],
        )

