"""
Documents endpoint — list and manage indexed documents.

GET  /api/v1/documents          — list documents
GET  /api/v1/documents/{id}     — get document details
DELETE /api/v1/documents/{id}   — delete document and its chunks

Phase 1: Stubs only. Phase 2+ will wire in DocumentService and repository layer.
"""

from fastapi import APIRouter, Request, status

from app.core.logging import get_logger
from app.schemas.common import PaginatedResponse
from app.schemas.documents import DocumentSummary

router = APIRouter()
logger = get_logger(__name__)


@router.get(
    "",
    response_model=PaginatedResponse[DocumentSummary],
    summary="List indexed documents",
    status_code=status.HTTP_200_OK,
)
async def list_documents(
    request: Request,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[DocumentSummary]:
    """List documents — Phase 1 stub."""
    logger.info("list_documents", page=page, page_size=page_size)
    return PaginatedResponse(
        data=[],
        total=0,
        page=page,
        page_size=page_size,
        request_id=request.state.request_id,
    )
