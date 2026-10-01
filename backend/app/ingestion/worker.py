"""Queue-triggered durable ingestion job execution."""

from __future__ import annotations

from typing import Any

from app.core.azure_clients import BlobStorageClient
from app.core.config import AppSettings
from app.core.logging import get_logger
from app.ingestion.factory import build_ingestion_service
from app.ingestion.job_store import IngestionJobStore
from app.ingestion.status_store import IngestionStatusStore

logger = get_logger(__name__)


def process_ingestion_job(
    job_id: str,
    *,
    dequeue_count: int,
    settings: AppSettings,
    job_store: IngestionJobStore | None = None,
) -> None:
    """Process one queue message, persisting retry/failure state before re-raising."""
    store = job_store or IngestionJobStore(settings)
    job = store.get(job_id)
    if job["status"] in {"completed", "failed"}:
        return
    store.update(job_id, status="processing", attempt=dequeue_count, message="Ingestion running.")
    result: dict[str, Any] = {}
    try:
        ingestion = build_ingestion_service(settings)
        if job["upload_blob"]:
            result = ingestion.ingest_raw_document(
                data=store.get_upload(job),
                filename=job["upload_blob"].rsplit("/", 1)[-1],
            )
            result = {
                "processed": int(result.get("status") == "indexed"),
                "skipped": int(result.get("status") == "skipped"),
                "failed": int(result.get("status") == "failed"),
                "details": (
                    [
                        {
                            "filename": result.get("filename", ""),
                            "status": "failed",
                            "error": result.get("error", "Document indexing failed."),
                        }
                    ]
                    if result.get("status") == "failed"
                    else []
                ),
            }
        elif job["source"] == "sharepoint":
            result = ingestion.ingest_from_sharepoint()
        else:
            result = ingestion.ingest_from_blob(document_ids=job["document_ids"] or None)

        failed = int(result.get("failed", 0))
        if result.get("status") == "error" or failed:
            raise RuntimeError(_failure_message(result))

        completed = store.update(
            job_id,
            status="completed",
            processed=int(result.get("processed", 0)),
            skipped=int(result.get("skipped", 0)),
            failed=0,
            message=(
                f"Processed: {result.get('processed', 0)}, "
                f"Skipped: {result.get('skipped', 0)}, Failed: 0"
            ),
            failure_details=[],
        )
        if job.get("upload_blob"):
            try:
                store.delete_upload(job)
            except Exception:
                logger.exception("ingestion_upload_cleanup_failed", job_id=job_id)
        IngestionStatusStore(BlobStorageClient(settings.azure_blob)).record(
            source=job["source"],
            trigger=job["trigger"],
            outcome="success",
            processed=completed["processed"],
            skipped=completed["skipped"],
            message=completed["message"],
        )
        logger.info("ingestion_job_completed", job_id=job_id)
    except Exception as exc:
        terminal = dequeue_count >= settings.ingestion_max_attempts
        message = str(exc)[:1000] or type(exc).__name__
        details = _failure_details(job, message, result)
        updated = store.update(
            job_id,
            status="failed" if terminal else "retrying",
            failed=max(1, int(result.get("failed", job.get("failed", 0)))),
            message="Ingestion failed." if terminal else "Ingestion failed; retry scheduled.",
            failure_details=details,
        )
        if terminal:
            IngestionStatusStore(BlobStorageClient(settings.azure_blob)).record(
                source=job["source"],
                trigger=job["trigger"],
                outcome="error",
                failed=updated["failed"],
                message=updated["message"],
            )
        logger.exception("ingestion_job_attempt_failed", job_id=job_id, terminal=terminal)
        raise


def _failure_message(result: dict[str, Any]) -> str:
    """Summarize failed files for queue retry diagnostics."""
    failures = [
        str(item.get("error") or item.get("reason") or "Ingestion failed.")
        for item in result.get("details", [])
        if item.get("status") == "failed"
    ]
    return "; ".join(failures)[:1000] or str(result.get("message") or "Ingestion failed.")


def _failure_details(
    job: dict[str, Any], message: str, result: dict[str, Any]
) -> list[dict[str, str]]:
    """Keep failure diagnostics useful while avoiding an unbounded status record."""
    failed_files = [
        {
            "filename": str(item.get("filename", "")),
            "error": str(item.get("error") or item.get("reason") or message)[:1000],
        }
        for item in result.get("details", [])
        if item.get("status") == "failed"
    ][:50]
    if failed_files:
        return failed_files
    filename = (job.get("upload_blob") or "").rsplit("/", 1)[-1]
    return [{"filename": filename, "error": message}] if filename else [{"error": message}]
