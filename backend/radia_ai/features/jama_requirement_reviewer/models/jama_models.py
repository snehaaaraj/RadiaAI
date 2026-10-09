"""Domain models for the Jama Connect REST integration.

These are the normalized shapes RadiaAI works with. The raw Jama API payloads
(``/rest/v1/projects``, ``/rest/v1/abstractitems``, ``/rest/v1/items/{id}``) are
mapped into these models by the service layer so the rest of the app never has
to know Jama's field-id conventions.
"""

from pydantic import BaseModel, Field, SecretStr


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
    rationale: str = Field(default="", description="Requirement rationale (HTML stripped)")
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


class JamaUserProfile(BaseModel):
    """The Jama user a set of API credentials authenticates as."""

    id: int
    username: str = ""
    email: str = ""
    display_name: str = ""
    active: bool = True


class JamaAccountLinkRequest(BaseModel):
    """Personal Jama API credentials submitted by the signed-in user."""

    client_id: str = Field(min_length=1, max_length=256, description="Jama API client ID")
    client_secret: SecretStr = Field(
        min_length=1, max_length=512, description="Jama API client secret"
    )


class JamaAccountStatus(BaseModel):
    """Whether the signed-in user can reach Jama, and as which Jama account."""

    linking_enabled: bool = Field(description="Server is configured for per-user Jama linking")
    linked: bool = False
    using_shared_account: bool = Field(
        default=False, description="Local development only: requests use the shared account"
    )
    jama_base_url: str | None = None
    jama_user_id: int | None = None
    jama_username: str | None = None
    jama_email: str | None = None
    jama_display_name: str | None = None
    linked_at: str | None = None
