"""
Ingestion endpoint - trigger document ingestion into Azure AI Search.

Endpoints are split across three routers so each gets the right protection when
mounted in ``app.api.v1.router``:

``router`` - ingestion management, requires ``Radia.Admin``:
    POST /api/v1/ingest                   - trigger blob or sharepoint ingestion
    POST /api/v1/ingest/upload            - upload a single document for ingestion
    GET  /api/v1/ingest/jobs/{job_id}     - per-job progress
    POST /api/v1/ingest/webhook/subscribe - (re)create the Graph subscription

``status_router`` - any signed-in Radia user:
    GET  /api/v1/ingest/status - outcome of the most recent ingestion run

``webhook_router`` - called by Microsoft Graph, which cannot send an Entra user
token. Each notification is authenticated by the subscription's ``clientState``
secret and checked against the persisted subscription instead:
    POST /api/v1/ingest/webhook
"""

from uuid import UUID

from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ingestion.job_store import IdempotencyConflictError, JobNotFoundError
from app.ingestion.validation import read_validated_upload
from app.schemas.common import APIResponse
from app.schemas.documents import (
    IngestionJobResponse,
    IngestionStatusResponse,
    IngestRequest,
    IngestResponse,
)
from radia_ai.features.jama_requirement_reviewer.dependencies.container import (
    IngestionJobStoreDep,
    IngestionStatusStoreDep,
    SharePointWebhookServiceDep,
)

router = APIRouter()
status_router = APIRouter()
webhook_router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "",
    response_model=APIResponse[IngestResponse],
    summary="Trigger document ingestion",
    description="Queues ingestion from blob storage or SharePoint into Azure AI Search.",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_ingestion(
    body: IngestRequest,
    request: Request,
    job_store: IngestionJobStoreDep,
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key", min_length=1, max_length=255
    ),
) -> APIResponse[IngestResponse]:
    """Durably queue ingestion from blob storage or SharePoint."""
    try:
        job, created = job_store.enqueue(
            source=body.source,
            trigger="manual",
            document_ids=body.document_ids,
            idempotency_key=idempotency_key,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except Exception as exc:
        logger.exception("ingestion_job_enqueue_failed", source=body.source)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Unable to queue ingestion job."
        ) from exc
    response = IngestResponse(
        job_id=job["job_id"],
        queued_count=1 if created else 0,
        message=job["message"],
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
    job_store: IngestionJobStoreDep,
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key", min_length=1, max_length=255
    ),
) -> APIResponse[IngestResponse]:
    """Validate, stage, and durably queue one document upload."""
    settings = getattr(request.app.state, "settings", None) or get_settings()
    data, filename = await read_validated_upload(
        file, max_bytes=settings.ingestion_max_upload_bytes
    )
    try:
        job, created = job_store.enqueue(
            source="upload",
            trigger="manual",
            upload=(data, filename, file.content_type or ""),
            idempotency_key=idempotency_key,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except Exception as exc:
        logger.exception("upload_ingestion_enqueue_failed", filename=filename)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Unable to queue ingestion job."
        ) from exc
    response = IngestResponse(
        job_id=job["job_id"],
        queued_count=1 if created else 0,
        message=job["message"],
    )
    return APIResponse(data=response, request_id=request.state.request_id)


@router.get(
    "/jobs/{job_id}",
    response_model=APIResponse[IngestionJobResponse],
    summary="Get an ingestion job",
)
async def get_ingestion_job(
    job_id: UUID,
    request: Request,
    job_store: IngestionJobStoreDep,
) -> APIResponse[IngestionJobResponse]:
    """Return durable per-job progress and failure details."""
    try:
        job = job_store.get(str(job_id))
    except JobNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ingestion job not found.") from exc
    return APIResponse(
        data=IngestionJobResponse.model_validate(job),
        request_id=request.state.request_id,
    )


@status_router.get(
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
    response = (
        IngestionStatusResponse.model_validate(latest) if latest else IngestionStatusResponse()
    )
    return APIResponse(data=response, request_id=request.state.request_id)


@webhook_router.post(
    "/webhook",
    response_model=None,
    include_in_schema=False,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sharepoint_webhook(
    request: Request,
    webhook_service: SharePointWebhookServiceDep,
) -> PlainTextResponse | dict[str, str]:
    """
    Receive Microsoft Graph change notifications for the SharePoint standards folder.

    Handles two distinct calls from Graph:
      1. Subscription validation handshake - a GET-style POST with a `validationToken`
         query param that must be echoed back as plain text within ~10 seconds.
      2. Change notifications - a JSON body with a `value` array of notification
         objects, each carrying the `clientState` secret set at subscription time.

    Each notification is checked against the persisted subscription before a
    durable queue message is created.
    """
    validation_token = request.query_params.get("validationToken")
    if validation_token is not None:
        logger.info("sharepoint_webhook_validation_handshake")
        return PlainTextResponse(content=validation_token, status_code=status.HTTP_200_OK)

    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid JSON payload.") from exc
    if not isinstance(body, dict) or not isinstance(body.get("value"), list):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Expected a notifications value array.")
    notifications = body["value"]
    if not notifications or len(notifications) > 100:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid notification batch size.")
    if not all(isinstance(item, dict) for item in notifications):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid notification item.")
    logger.info("sharepoint_webhook_notification_received", count=len(notifications))
    if not webhook_service.handle_notification(notifications):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Webhook notification validation failed.")
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
