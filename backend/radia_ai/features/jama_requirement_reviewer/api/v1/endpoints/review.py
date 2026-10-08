"""Requirements review endpoints."""

from anyio import to_thread
from fastapi import APIRouter, Query, Request, status

from app.core.logging import get_logger
from app.core.security import RadiaUserDep
from app.schemas.common import APIResponse
from radia_ai.features.jama_requirement_reviewer.dependencies.container import (
    RequirementDeltaReviewServiceDep,
    RequirementReviewServiceDep,
    ReviewHistoryServiceDep,
    ReviewVersionServiceDep,
)
from radia_ai.features.jama_requirement_reviewer.schemas.review import (
    DeltaReviewInput,
    DeltaReviewResponse,
    RequirementReviewInput,
    RequirementReviewResponse,
    ReviewVersionResponse,
)
from radia_ai.features.jama_requirement_reviewer.schemas.review_history import (
    ApplyFindingDispositionRequest,
    ReviewHistoryEntry,
    ReviewHistoryListResponse,
    ReviewWorkflow,
)

router = APIRouter()
logger = get_logger(__name__)

# The review pipeline (Azure OpenAI chat completions, AI Search, Blob Storage)
# uses synchronous SDK clients. Calling them directly from an ``async def``
# endpoint blocks the event loop, which serialises every concurrent request —
# a set review of 10 requirements would queue behind one another and time out.
# Offloading to the worker threadpool lets the requests genuinely run in
# parallel, so each result returns as soon as that requirement is done.


@router.get(
    "/version",
    response_model=APIResponse[ReviewVersionResponse],
    summary="Get review engine version metadata",
    description=(
        "Returns reviewer bundle version, prompt versions, standards versions, and "
        "configuration hash needed for reproducibility."
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
    summary="Run review for a single requirement",
    description=(
        "Runs language, structure, and verifiability reviewers and returns "
        "structured category status plus explainable findings."
    ),
    status_code=status.HTTP_200_OK,
)
async def review_requirement(
    body: RequirementReviewInput,
    request: Request,
    user: RadiaUserDep,
    service: RequirementReviewServiceDep,
    history_service: ReviewHistoryServiceDep,
) -> APIResponse[RequirementReviewResponse]:
    logger.info("requirement_review_requested", requirement_id=body.requirement_id or "")
    response = await to_thread.run_sync(service.review_requirement, body)
    review_id = await to_thread.run_sync(
        lambda: history_service.record_requirement_review(
            subject_id=body.requirement_id,
            response=response,
            owner_id=user.subject_key,
            owner_name=user.display_name or user.email,
        )
    )
    response = response.model_copy(update={"review_id": review_id})
    return APIResponse(data=response, request_id=request.state.request_id)


@router.post(
    "/delta",
    response_model=APIResponse[DeltaReviewResponse],
    summary="Run delta review between requirement revisions",
    description=(
        "Detects new, modified, and deleted requirements. "
        "Reviews only changed requirement items during incremental execution."
    ),
    status_code=status.HTTP_200_OK,
)
async def review_delta(
    body: DeltaReviewInput,
    request: Request,
    user: RadiaUserDep,
    service: RequirementDeltaReviewServiceDep,
    history_service: ReviewHistoryServiceDep,
) -> APIResponse[DeltaReviewResponse]:
    logger.info(
        "delta_review_requested",
        specification_id=body.specification_id or "",
        baseline_count=len(body.baseline_requirements),
        updated_count=len(body.updated_requirements),
    )
    response = await to_thread.run_sync(service.review_delta, body)
    review_id = await to_thread.run_sync(
        lambda: history_service.record_delta_review(
            subject_id=body.specification_id,
            response=response,
            owner_id=user.subject_key,
            owner_name=user.display_name or user.email,
        )
    )
    response = response.model_copy(update={"review_id": review_id})
    return APIResponse(data=response, request_id=request.state.request_id)


@router.get(
    "/history",
    response_model=APIResponse[ReviewHistoryListResponse],
    summary="List review history entries",
    description=(
        "Returns the caller's own reviews. Administrators (Radia.Admin) see every user's "
        "reviews, or only their own with mine_only=true."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_review_history(
    request: Request,
    user: RadiaUserDep,
    service: ReviewHistoryServiceDep,
    workflow: ReviewWorkflow | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    mine_only: bool = False,
) -> APIResponse[ReviewHistoryListResponse]:
    owner_id = None if user.is_admin and not mine_only else user.subject_key
    history = await to_thread.run_sync(
        lambda: service.list_history(workflow=workflow, limit=limit, owner_id=owner_id)
    )
    return APIResponse(data=history, request_id=request.state.request_id)


@router.post(
    "/history/{review_id}/disposition",
    response_model=APIResponse[ReviewHistoryEntry],
    summary="Apply reviewer disposition for a finding",
    description="Only the review's owner (or an administrator) can record dispositions.",
    status_code=status.HTTP_200_OK,
)
async def apply_finding_disposition(
    review_id: str,
    body: ApplyFindingDispositionRequest,
    request: Request,
    user: RadiaUserDep,
    service: ReviewHistoryServiceDep,
) -> APIResponse[ReviewHistoryEntry]:
    updated_entry = await to_thread.run_sync(
        lambda: service.apply_disposition(
            review_id=review_id,
            payload=body,
            reviewer_id=user.email or user.user_id,
            owner_id=None if user.is_admin else user.subject_key,
        )
    )
    return APIResponse(data=updated_entry, request_id=request.state.request_id)
