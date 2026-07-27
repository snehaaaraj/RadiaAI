"""Standards catalog endpoints."""

from fastapi import APIRouter, Request, status

from app.dependencies.container import StandardsServiceDep
from app.schemas.common import APIResponse
from app.schemas.standards import StandardsResponse

router = APIRouter()


@router.get(
    "",
    response_model=APIResponse[StandardsResponse],
    summary="List standards references used by deterministic reviewers",
    status_code=status.HTTP_200_OK,
)
async def list_standards(
    request: Request,
    service: StandardsServiceDep,
) -> APIResponse[StandardsResponse]:
    return APIResponse(data=service.list_standards(), request_id=request.state.request_id)

