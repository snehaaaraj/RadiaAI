"""
Ingestion endpoint — trigger document ingestion into Azure AI Search.

POST /api/v1/ingest         — trigger blob or sharepoint ingestion
POST /api/v1/ingest/upload  — upload a single document for ingestion
"""

import uuid

from fastapi import APIRouter, Request, UploadFile, File, status

from app.core.logging import get_logger
from app.schemas.common import APIResponse
from app.schemas.documents import IngestRequest, IngestResponse
from radia_ai.features.jama_requirement_reviewer.dependencies.container import IngestionServiceDep

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

    response = IngestResponse(
        job_id=job_id,
        queued_count=processed,
        message=f"Processed: {processed}, Skipped (unchanged): {skipped}, Failed: {failed}",
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
        message=f"Status: {result.get('status', 'unknown')} — {result.get('reason', result.get('error', 'OK'))}",
    )
    return APIResponse(data=response, request_id=request.state.request_id)
