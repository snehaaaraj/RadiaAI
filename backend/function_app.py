"""Azure Functions queue-trigger entry point for document ingestion."""

from __future__ import annotations

import json
from datetime import timedelta
from uuid import UUID

import azure.functions as func

from app.core.config import get_settings
from app.ingestion.job_store import IngestionJobStore
from app.ingestion.worker import process_ingestion_job

app = func.FunctionApp()


@app.function_name(name="ProcessIngestionJob")
@app.queue_trigger(
    arg_name="message",
    queue_name="%INGESTION_QUEUE_NAME%",
    connection="AZURE_BLOB_CONNECTION_STRING",
)
def process_ingestion_message(message: func.QueueMessage) -> None:
    """Run a durable ingestion job; queue retries and poison messages are host-managed."""
    body = json.loads(message.get_body().decode("utf-8"))
    job_id = body.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("Queue message must contain a job_id.")
    try:
        job_id = str(UUID(job_id))
    except ValueError as exc:
        raise ValueError("Queue message job_id must be a UUID.") from exc
    process_ingestion_job(
        job_id,
        dequeue_count=message.dequeue_count,
        settings=get_settings(),
    )


@app.function_name(name="RecoverUnsubmittedIngestionJobs")
@app.timer_trigger(
    schedule="0 */2 * * * *",
    arg_name="timer",
    use_monitor=True,
)
def recover_unsubmitted_ingestion_jobs(_: func.TimerRequest) -> None:
    """Repair the small Blob-write/Queue-send crash window in the producer."""
    settings = get_settings()
    recovered = IngestionJobStore(settings).redispatch_unsubmitted(older_than=timedelta(minutes=2))
    if recovered:
        from app.core.logging import get_logger

        get_logger(__name__).info("ingestion_jobs_redispatched", count=recovered)
