"""
Ingestion status store - persists the outcome of the most recent ingestion run.

Both the manual "Ingest Documents" button (POST /api/v1/ingest) and the automatic
SharePoint webhook trigger call `record()` after an ingestion run completes, so the
frontend can poll `GET /api/v1/ingest/status` and show a "last ingested" indicator
regardless of what triggered the run.

State is persisted as a small JSON blob in Azure Blob Storage so it survives across
stateless serverless invocations, matching the pattern used by
`app.ingestion.sharepoint_webhook.SharePointWebhookService`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict, cast

from azure.core.exceptions import ResourceNotFoundError

from app.core.azure_clients import BlobStorageClient
from app.core.logging import get_logger

logger = get_logger(__name__)

_STATE_BLOB_NAME = "system/ingestion-status.json"

IngestionTrigger = Literal["manual", "webhook"]
IngestionOutcome = Literal["success", "error"]


class IngestionStatus(TypedDict):
    timestamp: str
    source: str
    trigger: IngestionTrigger
    outcome: IngestionOutcome
    processed: int
    skipped: int
    failed: int
    message: str


class IngestionStatusStore:
    """Reads and writes the most recent ingestion run's outcome."""

    def __init__(self, blob_client: BlobStorageClient) -> None:
        self._blob = blob_client

    def record(
        self,
        *,
        source: str,
        trigger: IngestionTrigger,
        outcome: IngestionOutcome,
        processed: int = 0,
        skipped: int = 0,
        failed: int = 0,
        message: str = "",
    ) -> None:
        """Persist the outcome of an ingestion run as the latest status."""
        status: IngestionStatus = {
            "timestamp": datetime.now(UTC).isoformat(),
            "source": source,
            "trigger": trigger,
            "outcome": outcome,
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
            "message": message,
        }
        try:
            self._blob.upload_blob(
                _STATE_BLOB_NAME,
                json.dumps(status).encode("utf-8"),
                content_type="application/json",
            )
        except Exception:
            # Status tracking is best-effort - never let it fail the ingestion request.
            logger.exception("ingestion_status_record_failed")

    def get_latest(self) -> IngestionStatus | None:
        """Return the most recently recorded ingestion status, if any."""
        try:
            data = self._blob.download_blob(_STATE_BLOB_NAME)
            return cast(IngestionStatus, json.loads(data))
        except ResourceNotFoundError:
            return None
        except Exception:
            logger.exception("ingestion_status_load_failed")
            return None

    @staticmethod
    def outcome_from_result(result: dict[str, Any]) -> IngestionOutcome:
        """Derive a success/error outcome from an ingestion result dict."""
        if result.get("status") == "error":
            return "error"
        return "success"
