"""
Ingestion endpoint — trigger document ingestion jobs.

POST /api/v1/ingest      — trigger ingestion
GET  /api/v1/ingest/{job_id} — poll job status (Phase 2)

Phase 1: Stubs only. Phase 2 will wire in the IngestionService.
"""

import uuid

from fastapi import APIRouter, Request, status

from app.core.logging import get_logger
from app.schemas.common import APIResponse
from app.schemas.documents import IngestRequest, IngestResponse

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "",
    response_model=APIResponse[IngestResponse],
    summary="Trigger document ingestion",
    description="Queues documents from the specified source connector for indexing.",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_ingestion(
    body: IngestRequest,
    request: Request,
) -> APIResponse[IngestResponse]:
    """Ingestion trigger endpoint — Phase 1 stub."""
    job_id = str(uuid.uuid4())
    logger.info("ingest_triggered", source=body.source, job_id=job_id)

    stub_response = IngestResponse(
        job_id=job_id,
        queued_count=len(body.document_ids) if body.document_ids else 0,
        message="Ingestion pipeline not yet implemented (Phase 2)",
    )
    return APIResponse(data=stub_response, request_id=request.state.request_id)
