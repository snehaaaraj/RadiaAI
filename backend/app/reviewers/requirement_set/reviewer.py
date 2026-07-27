"""Requirement-set reviewer (skeleton)."""

from app.models.review_models import (
    RequirementReviewInput,
    RequirementSetReviewInput,
    ReviewerResult,
    ReviewStatus,
)
from app.reviewers.base import RequirementReviewer


class RequirementSetReviewer(RequirementReviewer):
    name = "requirement_set"
    reviewer_version = "1.0.0"
    prompt_version = "requirement-set.v1"
    standards_version = "internal-standards.v1"
    supports_individual_review = False
    supports_requirement_set_review = True

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

