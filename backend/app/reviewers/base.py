"""Reviewer interfaces for deterministic requirements review engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.review_models import (
        RequirementReviewInput,
        RequirementSetReviewInput,
        ReviewerResult,
    )


class RequirementReviewer(ABC):
    """Common interface for all reviewer modules."""

    name: str
    reviewer_version: str
    prompt_version: str
    standards_version: str
    supports_individual_review: bool = False
    supports_requirement_set_review: bool = False

    @abstractmethod
    def review_requirement(self, payload: RequirementReviewInput) -> ReviewerResult:
        """Review a single requirement."""

    @abstractmethod
    def review_requirement_set(self, payload: RequirementSetReviewInput) -> ReviewerResult:
        """Review an entire requirement set."""
