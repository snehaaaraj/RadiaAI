"""Service for storing review history and managing finding dispositions."""
# ruff: noqa: TC001

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.models.review_history_models import (
    ApplyFindingDispositionRequest,
    FindingDisposition,
    ReviewHistoryEntry,
    ReviewHistoryListResponse,
    ReviewWorkflow,
    create_delta_history_entry,
    create_requirement_history_entry,
)
from app.models.review_models import (
    DeltaReviewResponse,
    RequirementReviewResponse,
)
from app.repositories.review_history_repository import ReviewHistoryRepository


class ReviewHistoryService:
    """Handles recording and querying review history entries."""

    def __init__(self, repository: ReviewHistoryRepository) -> None:
        self._repository = repository

    def record_requirement_review(
        self,
        subject_id: str | None,
        response: RequirementReviewResponse,
    ) -> str:
        review_id = self._new_review_id()
        entry = create_requirement_history_entry(
            review_id=review_id,
            created_at=self._utc_now(),
            subject_id=subject_id,
            response=response,
        )
        self._repository.add_entry(entry)
        return review_id

    def record_delta_review(self, subject_id: str | None, response: DeltaReviewResponse) -> str:
        review_id = self._new_review_id()
        entry = create_delta_history_entry(
            review_id=review_id,
            created_at=self._utc_now(),
            subject_id=subject_id,
            response=response,
        )
        self._repository.add_entry(entry)
        return review_id

    def list_history(
        self,
        workflow: ReviewWorkflow | None = None,
        limit: int = 100,
    ) -> ReviewHistoryListResponse:
        entries = self._repository.list_entries(workflow=workflow, limit=limit)
        return ReviewHistoryListResponse(total=len(entries), entries=entries)

    def apply_disposition(
        self,
        review_id: str,
        payload: ApplyFindingDispositionRequest,
    ) -> ReviewHistoryEntry:
        disposition = FindingDisposition(
            finding_index=payload.finding_index,
            disposition=payload.disposition,
            reviewer_comment=payload.reviewer_comment,
            reviewer_id=payload.reviewer_id,
            updated_at=self._utc_now(),
        )
        return self._repository.apply_disposition(review_id=review_id, disposition=disposition)

    def _new_review_id(self) -> str:
        return f"rev-{uuid4()}"

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat()
