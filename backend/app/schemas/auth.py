"""Schemas for the authenticated-user endpoint."""

from typing import Literal

from pydantic import BaseModel, Field


class CurrentUserResponse(BaseModel):
    """The signed-in caller as seen by the API, used by the UI to adapt to permissions."""

    user_id: str
    email: str
    display_name: str
    auth_method: Literal["entra", "local"]
    roles: list[str] = Field(description="Effective roles, including implied roles")
    can_manage_documents: bool
    is_admin: bool
