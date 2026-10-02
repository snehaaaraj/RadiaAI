"""Durable Azure Storage Queue and Blob-backed ingestion job repository."""

from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueClient

from app.core.config import AppSettings
from app.core.logging import get_logger

logger = get_logger(__name__)
_JOB_PREFIX = "system/ingestion-jobs"
_UPLOAD_PREFIX = "system/ingestion-uploads"


class JobNotFoundError(LookupError):
    """Raised when a requested durable ingestion job does not exist."""


class IdempotencyConflictError(ValueError):
    """Raised when an idempotency key is reused for a different request."""


class IngestionJobStore:
    """Stores durable job state and sends small job references to Azure Queue."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._blob_service = BlobServiceClient.from_connection_string(
            settings.azure_blob.connection_string
        )
        self._container = self._blob_service.get_container_client(
            settings.azure_blob.container_name
        )
        self._queue = QueueClient.from_connection_string(
            settings.azure_blob.connection_string, settings.ingestion_queue_name
        )
        self._ready = False

    def ensure_ready(self) -> None:
        """Create the queue if needed; the document container must already exist."""
        if self._ready:
            return
        with suppress(ResourceExistsError):
            self._queue.create_queue()
        self._container.get_container_properties()
        self._ready = True

    def enqueue(
        self,
        *,
        source: str,
        trigger: Literal["manual", "webhook"],
        document_ids: list[str] | None = None,
        upload: tuple[bytes, str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Persist one job and enqueue its reference; return job and whether created."""
        self.ensure_ready()
        request_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "source": source,
                    "document_ids": document_ids or [],
                    "upload_hash": hashlib.sha256(upload[0]).hexdigest() if upload else None,
                    "filename": upload[1] if upload else None,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        job_id = (
            str(uuid.uuid5(uuid.NAMESPACE_URL, idempotency_key))
            if idempotency_key
            else str(uuid.uuid4())
        )
        now = datetime.now(UTC).isoformat()
        upload_blob = f"{_UPLOAD_PREFIX}/{job_id}/{upload[1]}" if upload else None
        job: dict[str, Any] = {
            "job_id": job_id,
            "source": source,
            "trigger": trigger,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "attempt": 0,
            "processed": 0,
            "skipped": 0,
            "failed": 0,
            "message": "Ingestion job queued.",
            "failure_details": [],
            "document_ids": document_ids or [],
            "upload_blob": upload_blob,
            "upload_content_type": upload[2] if upload else None,
            "request_fingerprint": request_fingerprint,
            "queue_submitted_at": None,
        }
        blob = self._container.get_blob_client(self._job_blob_name(job_id))
        try:
            blob.upload_blob(json.dumps(job).encode(), overwrite=False)
        except ResourceExistsError as exc:
            existing = self.get(job_id)
            if existing.get("request_fingerprint") != request_fingerprint:
                raise IdempotencyConflictError(
                    "Idempotency key was already used for a different ingestion request."
                ) from exc
            if (
                existing.get("status") == "failed"
                and existing.get("message") == "Unable to enqueue ingestion job."
            ):
                try:
                    if upload and upload_blob:
                        staged_blob = self._container.get_blob_client(upload_blob)
                        with suppress(ResourceExistsError):
                            staged_blob.upload_blob(
                                upload[0],
                                overwrite=False,
                                metadata={"content_sha256": hashlib.sha256(upload[0]).hexdigest()},
                            )
                    self._queue.send_message(json.dumps({"job_id": job_id}))
                    existing = self.update(
                        job_id,
                        status="queued",
                        queue_submitted_at=datetime.now(UTC).isoformat(),
                        message="Ingestion job queued.",
                        failure_details=[],
                    )
                except Exception as exc:
                    self.update(
                        job_id,
                        status="failed",
                        message="Unable to enqueue ingestion job.",
                        failure_details=[{"error": "Queue submission failed."}],
                    )
                    raise RuntimeError("Unable to enqueue ingestion job.") from exc
                return existing, True
            return existing, False

        try:
            if upload and upload_blob:
                self._container.get_blob_client(upload_blob).upload_blob(
                    upload[0],
                    overwrite=False,
                    metadata={"content_sha256": hashlib.sha256(upload[0]).hexdigest()},
                )
            self._queue.send_message(json.dumps({"job_id": job_id}))
        except Exception:
            self.update(
                job_id,
                status="failed",
                message="Unable to enqueue ingestion job.",
                failure_details=[{"error": "Queue submission failed."}],
            )
            raise
        try:
            job = self.update(job_id, queue_submitted_at=datetime.now(UTC).isoformat())
        except Exception:
            logger.exception("ingestion_job_dispatch_marker_failed", job_id=job_id)
        return job, True

    def redispatch_unsubmitted(self, *, older_than: timedelta) -> int:
        """Recover jobs persisted before a producer crashed while sending its queue message."""
        cutoff = datetime.now(UTC) - older_than
        recovered = 0
        for item in self._container.list_blobs(name_starts_with=f"{_JOB_PREFIX}/"):
            try:
                job_id = item.name.rsplit("/", 1)[-1].removesuffix(".json")
                job = self.get(job_id)
                created_at = datetime.fromisoformat(job["created_at"])
                enqueue_failed = (
                    job["status"] == "failed"
                    and job["message"] == "Unable to enqueue ingestion job."
                )
                if not (
                    (job["status"] == "queued" or enqueue_failed)
                    and job.get("queue_submitted_at") is None
                    and created_at <= cutoff
                ):
                    continue
                self._queue.send_message(json.dumps({"job_id": job_id}))
                self.update(
                    job_id,
                    status="queued",
                    queue_submitted_at=datetime.now(UTC).isoformat(),
                    message="Ingestion job queued.",
                    failure_details=[],
                )
                recovered += 1
            except Exception:
                logger.exception("ingestion_job_redispatch_failed", blob_name=item.name)
        return recovered

    def get(self, job_id: str) -> dict[str, Any]:
        """Return a job record or raise JobNotFoundError."""
        try:
            data = self._container.get_blob_client(self._job_blob_name(job_id)).download_blob()
            return cast(dict[str, Any], json.loads(data.readall()))
        except ResourceNotFoundError as exc:
            raise JobNotFoundError(job_id) from exc

    def update(self, job_id: str, **fields: object) -> dict[str, Any]:
        """Update mutable job state while preserving its original request data."""
        job = self.get(job_id)
        job.update(fields, updated_at=datetime.now(UTC).isoformat())
        self._container.get_blob_client(self._job_blob_name(job_id)).upload_blob(
            json.dumps(job).encode(), overwrite=True
        )
        return job

    def get_upload(self, job: dict[str, Any]) -> bytes:
        """Download the staged upload belonging to a job."""
        name = job.get("upload_blob")
        if not name:
            raise ValueError("Upload job is missing its staged blob reference.")
        return self._container.get_blob_client(name).download_blob().readall()

    def delete_upload(self, job: dict[str, Any]) -> None:
        """Remove staged bytes after successful indexing."""
        name = job.get("upload_blob")
        if name:
            self._container.get_blob_client(name).delete_blob(delete_snapshots="include")

    @staticmethod
    def _job_blob_name(job_id: str) -> str:
        return f"{_JOB_PREFIX}/{job_id}.json"
