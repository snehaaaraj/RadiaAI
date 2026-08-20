"""Certification reviewer — LLM+RAG powered."""

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    RequirementReviewInput,
    ReviewerResult,
    ReviewStatus,
)
from radia_ai.features.jama_requirement_reviewer.reviewers.base import RequirementReviewer


class CertificationReviewer(RequirementReviewer):
    name = "certification"
    reviewer_version = "2.0.0"
    prompt_version = "certification.v2"
    standards_version = "rag-live"
    supports_individual_review = True

    def review_requirement(self, payload: RequirementReviewInput) -> ReviewerResult:
        findings = []

        if self._llm_enhancer is not None:
            findings = self._llm_enhancer.generate_full_review(self.name, payload)

        overall = ReviewStatus.ACCEPTABLE
        if any(f.status == ReviewStatus.UNACCEPTABLE for f in findings):
            overall = ReviewStatus.UNACCEPTABLE
        elif any(f.status == ReviewStatus.REVISION_RECOMMENDED for f in findings):
            overall = ReviewStatus.REVISION_RECOMMENDED

        return ReviewerResult(
            reviewer=self.name,
            reviewer_version=self.reviewer_version,
            prompt_version=self.prompt_version,
            standards_version=self.standards_version,
            overall=overall,
            findings=findings,
        )