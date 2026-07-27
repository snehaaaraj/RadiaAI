"""Models for standards catalog APIs."""

from pydantic import BaseModel, Field


class StandardReference(BaseModel):
    """Single standards library metadata entry."""

    key: str
    name: str
    version: str
    source: str
    categories: list[str] = Field(default_factory=list)
    description: str = ""


class StandardsResponse(BaseModel):
    """Response payload for standards catalog API."""

    standards: list[StandardReference] = Field(default_factory=list)

