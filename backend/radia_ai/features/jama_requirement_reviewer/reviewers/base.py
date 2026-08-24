"""Reviewer interfaces for hybrid (deterministic + LLM) review engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from radia_ai.features.jama_requirement_reviewer.models.review_models import (
        RequirementReviewInput,
        ReviewerResult,
    )


class RequirementReviewer(ABC):
    """Common interface for all reviewer modules."""

    name: str
    reviewer_version: str
    prompt_version: str
    standards_version: str
    supports_individual_review: bool = False

    @abstractmethod
    def review_requirement(self, payload: RequirementReviewInput) -> ReviewerResult:
        """Review a single requirement (deterministic rules only)."""
