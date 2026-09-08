"""Domain models for the Jama Connect REST integration.

These are the normalized shapes RadiaAI works with. The raw Jama API payloads
(``/rest/v1/projects``, ``/rest/v1/abstractitems``, ``/rest/v1/items/{id}``) are
mapped into these models by the service layer so the rest of the app never has
to know Jama's field-id conventions.
"""

from pydantic import BaseModel, Field


class JamaProject(BaseModel):
    """A Jama project the user can scope a requirement search to."""

    id: int
    name: str
    project_key: str | None = None
    is_folder: bool = False


class JamaRequirementSummary(BaseModel):
    """Lightweight requirement entry returned by search / listing."""

    id: int
    document_key: str | None = Field(
        default=None, description="Human-facing Jama key, e.g. REQ-123"
    )
    global_id: str | None = None
    name: str = ""
    item_type_id: int | None = None
    project_id: int | None = None


class JamaRequirement(BaseModel):
    """Full requirement read directly from Jama for review."""

    id: int
    document_key: str | None = None
    global_id: str | None = None
    name: str = ""
    description: str = Field(default="", description="Requirement body text (HTML stripped)")
    status: str | None = None
    item_type_id: int | None = None
    project_id: int | None = None
    created_date: str | None = None
    modified_date: str | None = None
    web_url: str | None = Field(default=None, description="Deep link back to the item in Jama")
    fields: dict[str, object] = Field(
        default_factory=dict, description="Raw Jama field map for anything not normalized above"
    )


class JamaProjectList(BaseModel):
    """Response payload wrapping a list of projects."""

    projects: list[JamaProject] = Field(default_factory=list)


class JamaRequirementSearchResult(BaseModel):
    """Response payload wrapping requirement search results with paging info."""

    results: list[JamaRequirementSummary] = Field(default_factory=list)
    total: int = 0
    start_at: int = 0
    max_results: int = 0
