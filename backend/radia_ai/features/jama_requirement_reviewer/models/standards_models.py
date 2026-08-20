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
    sharepoint_url: str | None = None
    file_type: str | None = None
    last_modified: str | None = None
    file_size_bytes: int | None = None


class StandardsResponse(BaseModel):
    """Response payload for standards catalog API."""

    standards: list[StandardReference] = Field(default_factory=list)
    source: str = "registry"  # "sharepoint" | "registry" | "fallback"


