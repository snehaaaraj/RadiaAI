"""
Search endpoint — direct document search without LLM generation.

POST /api/v1/search

Phase 1: Returns a stub response to validate the API contract.
Phase 3: Will wire in the real Azure AI Search service.
"""

from fastapi import APIRouter, Depends, Request, status

from app.core.logging import get_logger
from app.schemas.common import APIResponse
from app.schemas.search import SearchRequest, SearchResponse

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
) -> APIResponse[SearchResponse]:
    """Direct search endpoint — Phase 1 stub."""
    logger.info("search_request", query_length=len(body.query), mode=body.mode, top_k=body.top_k)

    stub_response = SearchResponse(results=[], total=0, mode=body.mode)
    return APIResponse(data=stub_response, request_id=request.state.request_id)
