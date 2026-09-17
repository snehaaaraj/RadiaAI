"""
Ingestion endpoint - trigger document ingestion into Azure AI Search.

POST /api/v1/ingest         - trigger blob or sharepoint ingestion
POST /api/v1/ingest/upload  - upload a single document for ingestion
GET  /api/v1/ingest/status  - fetch the outcome of the most recent ingestion run
                              (manual or webhook-triggered), so the UI can show it.
POST /api/v1/ingest/webhook - Microsoft Graph change-notification receiver; auto-triggers
                              SharePoint ingestion when the standards folder changes.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, File, Request, UploadFile, status
from fastapi.responses import PlainTextResponse

from app.core.logging import get_logger
from app.schemas.common import APIResponse
from app.schemas.documents import IngestionStatusResponse, IngestRequest, IngestResponse
from radia_ai.features.jama_requirement_reviewer.dependencies.container import (
    IngestionServiceDep,
    IngestionStatusStoreDep,
    SharePointWebhookServiceDep,
)

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "",
    response_model=APIResponse[IngestResponse],
    summary="Trigger document ingestion",
    description="Ingests documents from blob storage or SharePoint into Azure AI Search.",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_ingestion(
    body: IngestRequest,
    request: Request,
    ingestion_service: IngestionServiceDep,
    status_store: IngestionStatusStoreDep,
) -> APIResponse[IngestResponse]:
    """Trigger ingestion from blob or SharePoint."""
    job_id = str(uuid.uuid4())
    logger.info("ingest_triggered", source=body.source, job_id=job_id)

    if body.source == "sharepoint":
        result = ingestion_service.ingest_from_sharepoint()
    else:
        result = ingestion_service.ingest_from_blob(
            document_ids=body.document_ids if body.document_ids else None,
        )

    processed = result.get("processed", 0)
    skipped = result.get("skipped", 0)
    failed = result.get("failed", 0)
    message = f"Processed: {processed}, Skipped (unchanged): {skipped}, Failed: {failed}"

    status_store.record(
        source=body.source,
        trigger="manual",
        outcome=status_store.outcome_from_result(result),
        processed=processed,
        skipped=skipped,
        failed=failed,
        message=message,
    )

    response = IngestResponse(
        job_id=job_id,
        queued_count=processed,
        message=message,
    )
    return APIResponse(data=response, request_id=request.state.request_id)


@router.post(
    "/upload",
    response_model=APIResponse[IngestResponse],
    summary="Upload and ingest a single document",
    description="Uploads a document file and indexes it into Azure AI Search.",
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_and_ingest(
    request: Request,
    ingestion_service: IngestionServiceDep,
    file: UploadFile = File(...),
) -> APIResponse[IngestResponse]:
    """Upload a single file for ingestion."""
    job_id = str(uuid.uuid4())
    data = await file.read()
    filename = file.filename or "unknown"
    logger.info("upload_ingest_triggered", filename=filename, job_id=job_id)

    result = ingestion_service.ingest_raw_document(data=data, filename=filename)

    response = IngestResponse(
        job_id=job_id,
        queued_count=1 if result.get("status") == "indexed" else 0,
        message=f"Status: {result.get('status', 'unknown')} - {result.get('reason', result.get('error', 'OK'))}",
    )
    return APIResponse(data=response, request_id=request.state.request_id)


@router.get(
    "/status",
    response_model=APIResponse[IngestionStatusResponse],
    summary="Get the outcome of the most recent ingestion run",
    description=(
        "Returns the timestamp, trigger (manual/webhook), and result counts for the "
        "most recent ingestion run, so the UI can show that documents were "
        "automatically re-ingested after a SharePoint change without requiring a "
        "manual click."
    ),
)
async def get_ingestion_status(
    request: Request,
    status_store: IngestionStatusStoreDep,
) -> APIResponse[IngestionStatusResponse]:
    """Return the most recently recorded ingestion status, if any."""
    latest = status_store.get_latest()
    response = IngestionStatusResponse(**latest) if latest else IngestionStatusResponse()
    return APIResponse(data=response, request_id=request.state.request_id)


@router.post(
    "/webhook",
    response_model=None,
    include_in_schema=False,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sharepoint_webhook(
    request: Request,
    webhook_service: SharePointWebhookServiceDep,
    background_tasks: BackgroundTasks,
) -> PlainTextResponse | dict[str, str]:
    """
    Receive Microsoft Graph change notifications for the SharePoint standards folder.

    Handles two distinct calls from Graph:
      1. Subscription validation handshake - a GET-style POST with a `validationToken`
         query param that must be echoed back as plain text within ~10 seconds.
      2. Change notifications - a JSON body with a `value` array of notification
         objects, each carrying the `clientState` secret set at subscription time.

    Ingestion (and subscription renewal) is deferred to a background task so the
    acknowledgement is returned to Graph immediately.
    """
    validation_token = request.query_params.get("validationToken")
    if validation_token is not None:
        logger.info("sharepoint_webhook_validation_handshake")
        return PlainTextResponse(content=validation_token, status_code=status.HTTP_200_OK)

    body = await request.json()
    notifications = body.get("value", [])
    logger.info("sharepoint_webhook_notification_accepted", count=len(notifications))
    background_tasks.add_task(webhook_service.handle_notification, notifications)
    return {"status": "accepted"}


@router.post(
    "/webhook/subscribe",
    response_model=APIResponse[dict[str, str]],
    summary="(Re)create the SharePoint change-notification subscription",
    description=(
        "Manually (re)creates or renews the Microsoft Graph subscription used to "
        "auto-trigger ingestion when SharePoint documents change. Useful for initial "
        "setup or recovering from a lapsed subscription."
    ),
    status_code=status.HTTP_202_ACCEPTED,
)
async def resubscribe_sharepoint_webhook(
    request: Request,
    webhook_service: SharePointWebhookServiceDep,
) -> APIResponse[dict[str, str]]:
    """Force-create or renew the SharePoint webhook subscription."""
    webhook_service.ensure_subscription(force=True)
    return APIResponse(
        data={"message": "Subscription refresh triggered"},
        request_id=request.state.request_id,
    )
