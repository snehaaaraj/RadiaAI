"""
Version-metadata reviewers for the consolidated LLM review.

All requirement analysis happens in a single consolidated LLM call, so these
modules carry no rule logic. They exist to publish the prompt, standards and
implementation versions behind each scored category, so a result can be traced
back to the configuration that produced it.
"""

from __future__ import annotations

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    REVIEW_CATEGORIES,
    RequirementReviewInput,
    ReviewCategory,
    ReviewerResult,
    ReviewStatus,
)
from radia_ai.features.jama_requirement_reviewer.reviewers.base import RequirementReviewer


class ConsolidatedCategoryReviewer(RequirementReviewer):
    """Publishes version metadata for one category of the consolidated review."""

    reviewer_version = "2.0.0"
    prompt_version = "consolidated.v1"
    standards_version = "rag-live"
    supports_individual_review = True

    def __init__(self, category: ReviewCategory) -> None:
        self.name = category.value

    def review_requirement(self, payload: RequirementReviewInput) -> ReviewerResult:
        """Return an empty result — findings come from the consolidated LLM call."""
        return ReviewerResult(
            reviewer=self.name,
            reviewer_version=self.reviewer_version,
            prompt_version=self.prompt_version,
            standards_version=self.standards_version,
            overall=ReviewStatus.ACCEPTABLE,
            findings=[],
        )


def build_category_reviewers() -> list[RequirementReviewer]:
    """Build one metadata reviewer per scored review category."""
    return [ConsolidatedCategoryReviewer(category) for category in REVIEW_CATEGORIES]
