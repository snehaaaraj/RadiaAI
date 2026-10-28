"""Service for storing review history and managing finding dispositions."""
# ruff: noqa: TC001

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.core.exceptions import ValidationError
from radia_ai.features.jama_requirement_reviewer.models.review_history_models import (
    ApplyFindingDispositionRequest,
    ApplyRecommendationDecisionRequest,
    FindingDisposition,
    RecommendationDecision,
    RecommendationDecisionStatus,
    ReviewHistoryEntry,
    ReviewHistoryListResponse,
    ReviewWorkflow,
    create_delta_history_entry,
    create_requirement_history_entry,
)
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    DeltaReviewResponse,
    RequirementReviewResponse,
)
from radia_ai.features.jama_requirement_reviewer.repositories.review_history_repository import (
    ReviewHistoryRepository,
)


class ReviewHistoryService:
    """Handles recording and querying review history entries."""

    def __init__(self, repository: ReviewHistoryRepository) -> None:
        self._repository = repository

    def record_requirement_review(
        self,
        subject_id: str | None,
        response: RequirementReviewResponse,
        owner_id: str | None = None,
        owner_name: str | None = None,
        workflow: ReviewWorkflow = ReviewWorkflow.REQUIREMENT,
    ) -> str:
        review_id = self._new_review_id()
        entry = create_requirement_history_entry(
            review_id=review_id,
            created_at=self._utc_now(),
            subject_id=subject_id,
            response=response,
            workflow=workflow,
        ).model_copy(update={"owner_id": owner_id, "owner_name": owner_name})
        self._repository.add_entry(entry)
        return review_id

    def record_delta_review(
        self,
        subject_id: str | None,
        response: DeltaReviewResponse,
        owner_id: str | None = None,
        owner_name: str | None = None,
    ) -> str:
        review_id = self._new_review_id()
        entry = create_delta_history_entry(
            review_id=review_id,
            created_at=self._utc_now(),
            subject_id=subject_id,
            response=response,
        ).model_copy(update={"owner_id": owner_id, "owner_name": owner_name})
        self._repository.add_entry(entry)
        return review_id

    def list_history(
        self,
        workflow: ReviewWorkflow | None = None,
        limit: int = 100,
        owner_id: str | None = None,
    ) -> ReviewHistoryListResponse:
        """List history; pass ``owner_id`` to restrict to one user (None = all users)."""
        entries = self._repository.list_entries(workflow=workflow, limit=limit, owner_id=owner_id)
        return ReviewHistoryListResponse(total=len(entries), entries=entries)

    def apply_disposition(
        self,
        review_id: str,
        payload: ApplyFindingDispositionRequest,
        reviewer_id: str | None = None,
        owner_id: str | None = None,
    ) -> ReviewHistoryEntry:
        """Apply a disposition as ``reviewer_id``; ``owner_id`` limits it to that user's review."""
        disposition = FindingDisposition(
            finding_index=payload.finding_index,
            disposition=payload.disposition,
            reviewer_comment=payload.reviewer_comment,
            reviewer_id=reviewer_id,
            updated_at=self._utc_now(),
        )
        return self._repository.apply_disposition(
            review_id=review_id, disposition=disposition, owner_id=owner_id
        )

    def apply_recommendation_decision(
        self,
        review_id: str,
        payload: ApplyRecommendationDecisionRequest,
        reviewer_id: str | None = None,
        owner_id: str | None = None,
    ) -> ReviewHistoryEntry:
        """Apply a decision on the final recommendation as ``reviewer_id``.

        ``owner_id`` limits the update to that user's review. A reason is required
        when rejecting, and a modified description is required when accepting with
        modifications.
        """
        if payload.decision == RecommendationDecisionStatus.REJECTED and not payload.reason.strip():
            raise ValidationError(
                "A reason is required to reject the final recommendation.",
                detail={"review_id": review_id},
            )
        if (
            payload.decision == RecommendationDecisionStatus.ACCEPTED_WITH_MODIFICATIONS
            and not (payload.modified_description or "").strip()
        ):
            raise ValidationError(
                "Modified description is required when accepting with modifications.",
                detail={"review_id": review_id},
            )

        decision = RecommendationDecision(
            decision=payload.decision,
            reason=payload.reason,
            modified_description=payload.modified_description,
            reviewer_id=reviewer_id,
            updated_at=self._utc_now(),
        )
        return self._repository.apply_recommendation_decision(
            review_id=review_id, decision=decision, owner_id=owner_id
        )

    def _new_review_id(self) -> str:
        return f"rev-{uuid4()}"

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat()
