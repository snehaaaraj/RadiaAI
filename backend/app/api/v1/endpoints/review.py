"""Requirements review endpoints."""

from fastapi import APIRouter, Request, status

from app.core.logging import get_logger
from app.dependencies.container import (
    RequirementDeltaReviewServiceDep,
    RequirementReviewServiceDep,
    RequirementSetReviewServiceDep,
    ReviewVersionServiceDep,
)
from app.schemas.common import APIResponse
from app.schemas.review import (
    DeltaReviewInput,
    DeltaReviewResponse,
    RequirementReviewInput,
    RequirementReviewResponse,
    RequirementSetReviewInput,
    RequirementSetReviewResponse,
    ReviewVersionResponse,
)

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


@router.post(
    "/requirement",
    response_model=APIResponse[RequirementReviewResponse],
    summary="Run deterministic review for a single requirement",
    description=(
        "Runs language, structure, and verifiability reviewers and returns "
        "structured category status plus explainable findings."
    ),
    status_code=status.HTTP_200_OK,
)
async def review_requirement(
    body: RequirementReviewInput,
    request: Request,
    service: RequirementReviewServiceDep,
) -> APIResponse[RequirementReviewResponse]:
    logger.info("requirement_review_requested", requirement_id=body.requirement_id or "")
    response = service.review_requirement(body)
    return APIResponse(data=response, request_id=request.state.request_id)


@router.post(
    "/requirement-set",
    response_model=APIResponse[RequirementSetReviewResponse],
    summary="Run deterministic review for a requirement set",
    description=(
        "Runs requirement set reviewers for duplicate, overlap, contradiction, "
        "traceability, and verification completeness checks."
    ),
    status_code=status.HTTP_200_OK,
)
async def review_requirement_set(
    body: RequirementSetReviewInput,
    request: Request,
    service: RequirementSetReviewServiceDep,
) -> APIResponse[RequirementSetReviewResponse]:
    logger.info(
        "requirement_set_review_requested",
        specification_id=body.specification_id or "",
        requirement_count=len(body.requirements),
    )
    response = service.review_requirement_set(body)
    return APIResponse(data=response, request_id=request.state.request_id)


@router.post(
    "/delta",
    response_model=APIResponse[DeltaReviewResponse],
    summary="Run deterministic delta review between requirement revisions",
    description=(
        "Detects new, modified, deleted requirements and changed trace links. "
        "Reviews only changed requirement items during incremental execution."
    ),
    status_code=status.HTTP_200_OK,
)
async def review_delta(
    body: DeltaReviewInput,
    request: Request,
    service: RequirementDeltaReviewServiceDep,
) -> APIResponse[DeltaReviewResponse]:
    logger.info(
        "delta_review_requested",
        specification_id=body.specification_id or "",
        baseline_count=len(body.baseline_requirements),
        updated_count=len(body.updated_requirements),
    )
    response = service.review_delta(body)
    return APIResponse(data=response, request_id=request.state.request_id)
