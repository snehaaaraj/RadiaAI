"""In-memory repository for review history records."""
# ruff: noqa: TC001

from __future__ import annotations

from threading import Lock

from app.core.exceptions import ValidationError
from app.models.review_history_models import FindingDisposition, ReviewHistoryEntry, ReviewWorkflow


class ReviewHistoryRepository:
    """Thread-safe in-memory repository for review history and dispositions."""

    def __init__(self) -> None:
        self._entries: list[ReviewHistoryEntry] = []
        self._lock = Lock()

    def add_entry(self, entry: ReviewHistoryEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def list_entries(
        self,
        workflow: ReviewWorkflow | None = None,
        limit: int = 100,
    ) -> list[ReviewHistoryEntry]:
        with self._lock:
            entries = list(self._entries)
        if workflow is not None:
            entries = [entry for entry in entries if entry.workflow == workflow]
        return list(reversed(entries))[:limit]

    def apply_disposition(
        self, review_id: str, disposition: FindingDisposition
    ) -> ReviewHistoryEntry:
        with self._lock:
            for index, entry in enumerate(self._entries):
                if entry.review_id != review_id:
                    continue
                if disposition.finding_index >= len(entry.findings):
                    raise ValidationError(
                        "Finding index is out of range for this review.",
                        detail={
                            "review_id": review_id,
                            "finding_index": disposition.finding_index,
                            "finding_count": len(entry.findings),
                        },
                    )

                updated_dispositions = [
                    item
                    for item in entry.dispositions
                    if item.finding_index != disposition.finding_index
                ]
                updated_dispositions.append(disposition)
                updated_entry = entry.model_copy(update={"dispositions": updated_dispositions})
                self._entries[index] = updated_entry
                return updated_entry

        raise ValidationError(
            "Review ID not found in history.",
            detail={"review_id": review_id},
        )
