"""
Search endpoint — document search powered by Azure AI Search.

POST /api/v1/search

Supports keyword, vector, and hybrid search against the indexed standards.
"""

from fastapi import APIRouter, Request, status

from app.core.logging import get_logger
from app.schemas.common import APIResponse
from app.schemas.search import SearchRequest, SearchResponse, SearchResult
from radia_ai.features.jama_requirement_reviewer.dependencies.container import SearchServiceDep

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "",
    response_model=APIResponse[SearchResponse],
    summary="Search indexed documents",
    description="Runs keyword, vector, or hybrid search against the Azure AI Search index.",
    status_code=status.HTTP_200_OK,
)
async def search(
    body: SearchRequest,
    request: Request,
    search_service: SearchServiceDep,
) -> APIResponse[SearchResponse]:
    """Search indexed documents using Azure AI Search."""
    logger.info("search_request", query_length=len(body.query), mode=body.mode, top_k=body.top_k)

    raw_results = search_service.search(
        query=body.query,
        mode=body.mode,
        top_k=body.top_k,
        filters=body.filters if body.filters else None,
    )

    results = [
        SearchResult(
            chunk_id=r["chunk_id"],
            score=r.get("score", 0.0),
            source=r.get("source", ""),
            filename=r.get("filename", ""),
            document_type=r.get("document_type", ""),
            section=r.get("section", ""),
            page_number=r.get("page_number"),
            content=r.get("content", ""),
            highlights=r.get("highlights", []),
        )
        for r in raw_results
    ]

    response = SearchResponse(results=results, total=len(results), mode=body.mode)
    return APIResponse(data=response, request_id=request.state.request_id)
