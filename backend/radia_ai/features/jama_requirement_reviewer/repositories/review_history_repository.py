"""Blob-backed repository for review history records.

Each review entry is stored as a JSON blob under the ``review-history/``
prefix, keyed by its ``review_id``.  This makes the repository stateless
across Vercel serverless invocations while reusing the Azure Blob Storage
account already configured for the project.

Entries older than 10 days are automatically deleted during list operations.
"""
# ruff: noqa: TC001

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from azure.core.exceptions import ResourceNotFoundError

from app.core.azure_clients import BlobStorageClient
from app.core.exceptions import ValidationError
from radia_ai.features.jama_requirement_reviewer.models.review_history_models import (
    FindingDisposition,
    ReviewHistoryEntry,
    ReviewWorkflow,
)

logger = logging.getLogger(__name__)

_BLOB_PREFIX = "review-history/"
_RETENTION_DAYS = 10


class ReviewHistoryRepository:
    """Blob Storage-backed repository for review history and dispositions."""

    def __init__(self, blob_client: BlobStorageClient) -> None:
        self._blob = blob_client

    # -- helpers -------------------------------------------------------------

    def _blob_name(self, review_id: str) -> str:
        return f"{_BLOB_PREFIX}{review_id}.json"

    def _put(self, entry: ReviewHistoryEntry) -> None:
        self._blob.upload_blob(
            self._blob_name(entry.review_id),
            entry.model_dump_json().encode(),
            content_type="application/json",
        )

    def _get(self, review_id: str) -> ReviewHistoryEntry | None:
        try:
            data = self._blob.download_blob(self._blob_name(review_id))
        except (ResourceNotFoundError, Exception):
            return None
        return ReviewHistoryEntry.model_validate_json(data)

    # -- public API (unchanged signatures) -----------------------------------

    def add_entry(self, entry: ReviewHistoryEntry) -> None:
        self._put(entry)

    def cleanup_old_entries(self) -> int:
        """Delete entries older than RETENTION_DAYS. Returns count deleted."""
        cutoff = datetime.now(UTC) - timedelta(days=_RETENTION_DAYS)
        blobs = self._blob.list_blobs(prefix=_BLOB_PREFIX)
        deleted = 0

        for blob_meta in blobs:
            last_modified_str = blob_meta.get("last_modified")
            if not last_modified_str:
                continue

            try:
                last_modified = datetime.fromisoformat(last_modified_str.replace("Z", "+00:00"))
                if last_modified < cutoff:
                    self._blob.delete_blob(blob_meta["name"])
                    deleted += 1
                    logger.info(
                        "deleted_old_review_history",
                        extra={
                            "blob": blob_meta["name"],
                            "age_days": (datetime.now(UTC) - last_modified).days,
                        },
                    )
            except Exception:
                logger.warning("cleanup_failed_for_blob", extra={"blob": blob_meta["name"]})
                continue

        return deleted

    def list_entries(
        self,
        workflow: ReviewWorkflow | None = None,
        limit: int = 100,
    ) -> list[ReviewHistoryEntry]:
        # Auto-cleanup on every list call (lightweight, runs async in background on Vercel)
        try:
            deleted = self.cleanup_old_entries()
            if deleted > 0:
                logger.info("review_history_cleanup", extra={"deleted_count": deleted})
        except Exception:
            logger.exception("review_history_cleanup_failed")

        blobs = self._blob.list_blobs(prefix=_BLOB_PREFIX)
        # Sort newest-first by last_modified (already ISO strings)
        blobs.sort(key=lambda b: b.get("last_modified", ""), reverse=True)

        entries: list[ReviewHistoryEntry] = []
        for blob_meta in blobs:
            if len(entries) >= limit:
                break
            try:
                data = self._blob.download_blob(blob_meta["name"])
                entry = ReviewHistoryEntry.model_validate_json(data)
            except Exception:
                logger.warning("skipping_corrupt_history_blob", extra={"blob": blob_meta["name"]})
                continue
            if workflow is not None and entry.workflow != workflow:
                continue
            entries.append(entry)
        return entries

    def apply_disposition(
        self, review_id: str, disposition: FindingDisposition
    ) -> ReviewHistoryEntry:
        entry = self._get(review_id)
        if entry is None:
            raise ValidationError(
                "Review ID not found in history.",
                detail={"review_id": review_id},
            )

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
            item for item in entry.dispositions if item.finding_index != disposition.finding_index
        ]
        updated_dispositions.append(disposition)
        updated_entry = entry.model_copy(update={"dispositions": updated_dispositions})
        self._put(updated_entry)
        return updated_entry
