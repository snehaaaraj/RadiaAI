"""Service for storing review history and managing finding dispositions."""
# ruff: noqa: TC001

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.core.exceptions import JamaWriteConflictError, ValidationError
from radia_ai.features.jama_requirement_reviewer.models.review_history_models import (
    ApplyFindingDispositionRequest,
    ApplyRecommendationDecisionRequest,
    FindingDisposition,
    JamaWriteRecord,
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
    RecommendationStatus,
    RequirementReviewResponse,
)
from radia_ai.features.jama_requirement_reviewer.repositories.review_history_repository import (
    ReviewHistoryRepository,
)
from radia_ai.features.jama_requirement_reviewer.services.jama_service import JamaService


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
        jama_item_id: int | None = None,
        jama_modified_date: str | None = None,
    ) -> str:
        review_id = self._new_review_id()
        entry = create_requirement_history_entry(
            review_id=review_id,
            created_at=self._utc_now(),
            subject_id=subject_id,
            response=response,
            workflow=workflow,
            jama_item_id=jama_item_id,
            jama_modified_date=jama_modified_date,
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

    def write_decision_to_jama(
        self,
        review_id: str,
        jama_service: JamaService,
        written_by: str | None = None,
        owner_id: str | None = None,
    ) -> ReviewHistoryEntry:
        """Write the reviewer-approved Description back to the reviewed Jama item.

        The text written is taken from the *stored* decision, never from the client:
        "Ready to replace" writes the final recommended Description exactly, and
        "Accept, but modify" writes the reviewer's modified Description exactly. A
        rejected recommendation is never written. Only the Description field changes.
        """
        entry = self._repository.get_entry(review_id, owner_id=owner_id)
        if entry.jama_item_id is None:
            raise ValidationError(
                "This review was not run on a requirement pulled from Jama, so there is "
                "no Jama item to update.",
                detail={"review_id": review_id},
            )
        decision = entry.recommendation_decision
        if decision is None:
            raise ValidationError(
                "Save a decision on the final recommendation before writing to Jama.",
                detail={"review_id": review_id},
            )

        description = self._approved_description(entry, decision)

        expected_modified = (
            entry.jama_write.modified_date if entry.jama_write else entry.jama_modified_date
        )
        if expected_modified:
            current = jama_service.get_requirement(entry.jama_item_id)
            if current.modified_date and current.modified_date != expected_modified:
                raise JamaWriteConflictError(
                    "This Jama item was changed after it was reviewed. Pull it from Jama "
                    "again and re-run the review so the latest version is not overwritten.",
                    detail={
                        "review_id": review_id,
                        "item_id": entry.jama_item_id,
                        "reviewed_modified_date": expected_modified,
                        "current_modified_date": current.modified_date,
                    },
                )

        updated = jama_service.update_requirement_description(entry.jama_item_id, description)
        record = JamaWriteRecord(
            item_id=updated.id,
            document_key=updated.document_key,
            decision=decision.decision,
            description=description,
            written_by=written_by,
            written_at=self._utc_now(),
            web_url=updated.web_url,
            modified_date=updated.modified_date,
        )
        return self._repository.record_jama_write(review_id, record, owner_id=owner_id)

    @staticmethod
    def _approved_description(entry: ReviewHistoryEntry, decision: RecommendationDecision) -> str:
        if decision.decision == RecommendationDecisionStatus.READY_TO_REPLACE:
            recommendation = entry.final_recommendation
            text = recommendation.recommended_description if recommendation else None
            if recommendation is None or recommendation.status == RecommendationStatus.FAILED:
                text = None
        elif decision.decision == RecommendationDecisionStatus.ACCEPTED_WITH_MODIFICATIONS:
            text = decision.modified_description
        else:
            raise ValidationError(
                "A rejected recommendation is not written to Jama.",
                detail={"review_id": entry.review_id},
            )
        if not (text or "").strip():
            raise ValidationError(
                "There is no approved Description to write to Jama.",
                detail={"review_id": entry.review_id},
            )
        return (text or "").strip()

    def _new_review_id(self) -> str:
        return f"rev-{uuid4()}"

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat()
