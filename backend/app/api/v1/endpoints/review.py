"""Requirements review endpoints."""

from fastapi import APIRouter, Request, status

from app.core.logging import get_logger
from app.dependencies.container import ReviewVersionServiceDep
from app.schemas.common import APIResponse
from app.schemas.review import ReviewVersionResponse

router = APIRouter()
logger = get_logger(__name__)


@router.get(
    "/version",
    response_model=APIResponse[ReviewVersionResponse],
    summary="Get deterministic review engine version metadata",
    description=(
        "Returns reviewer bundle version, prompt versions, standards versions, and "
        "determinism configuration hash needed for reproducibility."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_review_version(
    request: Request,
    service: ReviewVersionServiceDep,
) -> APIResponse[ReviewVersionResponse]:
    logger.info("review_version_requested")
    version = service.get_review_version()
    return APIResponse(data=version, request_id=request.state.request_id)
