"""Standards catalog endpoints."""

from fastapi import APIRouter, Request, status

from app.schemas.common import APIResponse
from radia_ai.features.jama_requirement_reviewer.dependencies.container import StandardsServiceDep
from radia_ai.features.jama_requirement_reviewer.schemas.standards import StandardsResponse

router = APIRouter()


@router.get(
    "",
    response_model=APIResponse[StandardsResponse],
    summary="List standards references used by reviewers",
    status_code=status.HTTP_200_OK,
)
async def list_standards(
    request: Request,
    service: StandardsServiceDep,
) -> APIResponse[StandardsResponse]:
    return APIResponse(data=service.list_standards(), request_id=request.state.request_id)
