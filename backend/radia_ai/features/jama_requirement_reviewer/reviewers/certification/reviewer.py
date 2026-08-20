"""Certification reviewer (skeleton)."""

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    RequirementReviewInput,
    ReviewerResult,
    ReviewStatus,
)
from radia_ai.features.jama_requirement_reviewer.reviewers.base import RequirementReviewer


class CertificationReviewer(RequirementReviewer):
    name = "certification"
    reviewer_version = "1.0.0"
    prompt_version = "certification.v1"
    standards_version = "cert-guidance.v1"
    supports_individual_review = False

    def review_requirement(self, payload: RequirementReviewInput) -> ReviewerResult:
        return ReviewerResult(
            reviewer=self.name,
            reviewer_version=self.reviewer_version,
            prompt_version=self.prompt_version,
            standards_version=self.standards_version,
            overall=ReviewStatus.ACCEPTABLE,
            findings=[],
        )


