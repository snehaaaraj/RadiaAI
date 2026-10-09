"""Jama Connect integration endpoints.

Every Jama call runs as the signed-in user's *own* linked Jama account, so Jama
enforces that user's project permissions. Users link their account once via
``PUT /jama/account`` with personal API credentials from their Jama profile.
Credentials are verified, encrypted, and never returned to the browser.
"""

from anyio import to_thread
from fastapi import APIRouter, Query, Request, status

from app.core.logging import get_logger
from app.core.security import RadiaUserDep
from app.schemas.common import APIResponse
from radia_ai.features.jama_requirement_reviewer.dependencies.container import (
    JamaAccountServiceDep,
    JamaServiceDep,
)
from radia_ai.features.jama_requirement_reviewer.schemas.jama import (
    JamaAccountLinkRequest,
    JamaAccountStatus,
    JamaProjectList,
    JamaRequirement,
    JamaRequirementSearchResult,
)

router = APIRouter()
logger = get_logger(__name__)


@router.get(
    "/account",
    response_model=APIResponse[JamaAccountStatus],
    summary="Get the signed-in user's Jama link status",
    status_code=status.HTTP_200_OK,
)
async def get_jama_account(
    request: Request,
    user: RadiaUserDep,
    account_service: JamaAccountServiceDep,
) -> APIResponse[JamaAccountStatus]:
    result = await to_thread.run_sync(lambda: account_service.status(user))
    return APIResponse(data=result, request_id=request.state.request_id)


@router.put(
    "/account",
    response_model=APIResponse[JamaAccountStatus],
    summary="Link the signed-in user's Jama account",
    description=(
        "Verifies personal Jama API credentials (Jama profile -> Set API Credentials) "
        "against Jama, checks they belong to the signed-in Microsoft user, and stores them "
        "encrypted. Replaces any previously linked credentials."
    ),
    status_code=status.HTTP_200_OK,
)
async def link_jama_account(
    body: JamaAccountLinkRequest,
    request: Request,
    user: RadiaUserDep,
    account_service: JamaAccountServiceDep,
) -> APIResponse[JamaAccountStatus]:
    result = await to_thread.run_sync(lambda: account_service.link(user, body))
    return APIResponse(data=result, request_id=request.state.request_id)


@router.delete(
    "/account",
    response_model=APIResponse[JamaAccountStatus],
    summary="Unlink the signed-in user's Jama account",
    status_code=status.HTTP_200_OK,
)
async def unlink_jama_account(
    request: Request,
    user: RadiaUserDep,
    account_service: JamaAccountServiceDep,
) -> APIResponse[JamaAccountStatus]:
    result = await to_thread.run_sync(lambda: account_service.unlink(user))
    return APIResponse(data=result, request_id=request.state.request_id)


@router.get(
    "/projects",
    response_model=APIResponse[JamaProjectList],
    summary="List Jama projects",
    description="Returns projects visible to the signed-in user's linked Jama account.",
    status_code=status.HTTP_200_OK,
)
async def list_jama_projects(
    request: Request,
    service: JamaServiceDep,
) -> APIResponse[JamaProjectList]:
    result = await to_thread.run_sync(service.list_projects)
    return APIResponse(data=result, request_id=request.state.request_id)


@router.get(
    "/requirements",
    response_model=APIResponse[JamaRequirementSearchResult],
    summary="Search Jama requirements",
    description=(
        "Search or list Jama items, optionally scoped to a project and a free-text "
        "query, so a user can choose a requirement by ID."
    ),
    status_code=status.HTTP_200_OK,
)
async def search_jama_requirements(
    request: Request,
    service: JamaServiceDep,
    project_id: int | None = Query(default=None, description="Scope search to a project id"),
    contains: str | None = Query(default=None, description="Free-text query"),
    item_type_id: int | None = Query(default=None, description="Filter by Jama item type id"),
    start_at: int = Query(default=0, ge=0, description="Zero-based paging offset"),
    max_results: int = Query(default=50, ge=1, le=50, description="Page size (max 50)"),
) -> APIResponse[JamaRequirementSearchResult]:
    result = await to_thread.run_sync(
        lambda: service.search_requirements(
            project_id=project_id,
            contains=contains,
            item_type_id=item_type_id,
            start_at=start_at,
            max_results=max_results,
        )
    )
    return APIResponse(data=result, request_id=request.state.request_id)


@router.get(
    "/requirements/{item_id}",
    response_model=APIResponse[JamaRequirement],
    summary="Read a Jama requirement",
    description="Reads a single Jama item by numeric id and returns its normalized content.",
    status_code=status.HTTP_200_OK,
)
async def get_jama_requirement(
    item_id: int,
    request: Request,
    service: JamaServiceDep,
) -> APIResponse[JamaRequirement]:
    result = await to_thread.run_sync(lambda: service.get_requirement(item_id))
    return APIResponse(data=result, request_id=request.state.request_id)
