"""List indexed documents and retrieve or delete their chunks."""

from typing import Literal

from anyio import to_thread
from fastapi import APIRouter, Query, Request, status

from app.core.exceptions import DocumentNotFoundError
from app.core.logging import get_logger
from app.core.security import DocumentAdminDep
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.documents import (
    DocumentDeleteResponse,
    DocumentDetail,
    DocumentSummary,
)
from radia_ai.features.jama_requirement_reviewer.dependencies.container import (
    DocumentCatalogRepositoryDep,
    SearchServiceDep,
)

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
    catalog: DocumentCatalogRepositoryDep,
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=20, ge=1, le=100),
    source: str | None = Query(default=None, min_length=1, max_length=100),
    query: str | None = Query(default=None, min_length=1, max_length=200),
    sort_by: Literal["filename", "source", "chunk_count", "ingested_at"] = "filename",
    sort_order: Literal["asc", "desc"] = "asc",
) -> PaginatedResponse[DocumentSummary]:
    """List catalog records with validated paging, filtering, and sorting."""
    documents, total = await to_thread.run_sync(
        lambda: catalog.list(
            page=page,
            page_size=page_size,
            source=source,
            query=query,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    )
    logger.info(
        "documents_listed",
        page=page,
        page_size=page_size,
        total=total,
        source=source,
        query=query,
    )
    return PaginatedResponse(
        data=documents,
        total=total,
        page=page,
        page_size=page_size,
        request_id=request.state.request_id,
    )


@router.get(
    "/{document_id}",
    response_model=APIResponse[DocumentDetail],
    summary="Get indexed document details",
    status_code=status.HTTP_200_OK,
)
async def get_document(
    document_id: str,
    request: Request,
    catalog: DocumentCatalogRepositoryDep,
    search: SearchServiceDep,
) -> APIResponse[DocumentDetail]:
    """Return document-level metadata and all indexed chunks."""
    document = await to_thread.run_sync(lambda: catalog.get(document_id))
    if document is None:
        raise DocumentNotFoundError(f"Indexed document {document_id} was not found.")
    chunks = await to_thread.run_sync(lambda: search.get_document_chunks(document_id))
    return APIResponse(
        data=DocumentDetail.model_validate({**document.model_dump(), "chunks": chunks}),
        request_id=request.state.request_id,
    )


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    summary="Delete an indexed document",
    status_code=status.HTTP_200_OK,
)
async def delete_document(
    document_id: str,
    catalog: DocumentCatalogRepositoryDep,
    search: SearchServiceDep,
    _admin: DocumentAdminDep,
) -> DocumentDeleteResponse:
    """Delete the indexed chunks and catalog row, leaving the source file untouched."""
    document = await to_thread.run_sync(lambda: catalog.get(document_id))
    if document is None:
        raise DocumentNotFoundError(f"Indexed document {document_id} was not found.")
    await to_thread.run_sync(lambda: search.delete_documents_by_file_hash(document_id))
    await to_thread.run_sync(lambda: catalog.delete(document_id))
    logger.info("indexed_document_deleted", document_id=document_id)
    return DocumentDeleteResponse(
        document_id=document_id,
        message="Indexed document and chunks deleted; source file was not changed.",
    )
