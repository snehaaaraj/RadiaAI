"""
Auth endpoint - describes the signed-in user.

GET /api/v1/auth/me
"""

from fastapi import APIRouter, Request, status

from app.core.security import RadiaUserDep
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import APIResponse

router = APIRouter()


@router.get(
    "/me",
    response_model=APIResponse[CurrentUserResponse],
    summary="Get the signed-in user",
    status_code=status.HTTP_200_OK,
)
async def get_me(request: Request, user: RadiaUserDep) -> APIResponse[CurrentUserResponse]:
    return APIResponse(
        data=CurrentUserResponse(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            email=user.email,
            display_name=user.display_name,
            auth_method=user.auth_method,
            roles=sorted(user.effective_roles),
            can_manage_documents=user.is_admin,
            is_admin=user.is_admin,
        ),
        request_id=request.state.request_id,
    )
