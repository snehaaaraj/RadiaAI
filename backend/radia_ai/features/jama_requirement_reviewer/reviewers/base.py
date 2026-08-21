"""Reviewer interfaces for hybrid (deterministic + LLM) review engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.rag.llm_review_enhancer import LLMReviewEnhancer
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

    def __init__(self, llm_enhancer: LLMReviewEnhancer | None = None) -> None:
        self._llm_enhancer = llm_enhancer

    @abstractmethod
    def review_requirement(self, payload: RequirementReviewInput) -> ReviewerResult:
        """Review a single requirement."""

