"""Requirements review endpoints."""

from fastapi import APIRouter, Request, status

from app.core.logging import get_logger
from app.dependencies.container import (
    RequirementDeltaReviewServiceDep,
    RequirementReviewServiceDep,
    ReviewHistoryServiceDep,
    ReviewVersionServiceDep,
)
from app.schemas.common import APIResponse
from app.schemas.review import (
    DeltaReviewInput,
    DeltaReviewResponse,
    RequirementReviewInput,
    RequirementReviewResponse,
    ReviewVersionResponse,
)
from app.schemas.review_history import (
    ApplyFindingDispositionRequest,
    ReviewHistoryEntry,
    ReviewHistoryListResponse,
    ReviewWorkflow,
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
    history_service: ReviewHistoryServiceDep,
) -> APIResponse[RequirementReviewResponse]:
    logger.info("requirement_review_requested", requirement_id=body.requirement_id or "")
    response = service.review_requirement(body)
    review_id = history_service.record_requirement_review(
        subject_id=body.requirement_id, response=response
    )
    response = response.model_copy(update={"review_id": review_id})
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
    history_service: ReviewHistoryServiceDep,
) -> APIResponse[DeltaReviewResponse]:
    logger.info(
        "delta_review_requested",
        specification_id=body.specification_id or "",
        baseline_count=len(body.baseline_requirements),
        updated_count=len(body.updated_requirements),
    )
    response = service.review_delta(body)
    review_id = history_service.record_delta_review(
        subject_id=body.specification_id, response=response
    )
    response = response.model_copy(update={"review_id": review_id})
    return APIResponse(data=response, request_id=request.state.request_id)


@router.get(
    "/history",
    response_model=APIResponse[ReviewHistoryListResponse],
    summary="List review history entries",
    status_code=status.HTTP_200_OK,
)
async def get_review_history(
    request: Request,
    service: ReviewHistoryServiceDep,
    workflow: ReviewWorkflow | None = None,
    limit: int = 100,
) -> APIResponse[ReviewHistoryListResponse]:
    history = service.list_history(workflow=workflow, limit=limit)
    return APIResponse(data=history, request_id=request.state.request_id)


@router.post(
    "/history/{review_id}/disposition",
    response_model=APIResponse[ReviewHistoryEntry],
    summary="Apply reviewer disposition for a finding",
    status_code=status.HTTP_200_OK,
)
async def apply_finding_disposition(
    review_id: str,
    body: ApplyFindingDispositionRequest,
    request: Request,
    service: ReviewHistoryServiceDep,
) -> APIResponse[ReviewHistoryEntry]:
    updated_entry = service.apply_disposition(review_id=review_id, payload=body)
    return APIResponse(data=updated_entry, request_id=request.state.request_id)
