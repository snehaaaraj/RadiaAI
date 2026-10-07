"""Vitech GENESYS connector - **placeholder, not implemented**.

GENESYS is the Model-Based Systems Engineering tool from Vitech, now part of
Zuken. It is **not** Genesys Cloud CX, the contact-centre platform that shares
the name - different vendor, different API entirely.

Why this is a placeholder
-------------------------
Vitech's public API reference is no longer reachable: the "Getting Started with
the GENESYS API" PDF and the AdminTools REST help page now redirect to Zuken
marketing pages, and the real reference sits behind a customer login or on each
instance's own Swagger UI. What remains publicly documented is only that the
API authenticates at ``api/v1/token`` and is organised into Authentication,
Projects, Entities and Schemas sections.

Rather than ship a speculative HTTP client against an unverified contract, this
module keeps only what is safe to commit:

  - :class:`GenesysSettings`, so ``GENESYS_*`` configuration is already wired
    and a ``.env`` written today stays valid.
  - The model shapes the real connector is expected to return, documenting the
    intended contract.
  - A :class:`GenesysClient` whose operations raise
    :class:`ConnectorNotImplementedError`.

No GENESYS tools are registered on the MCP server, so the advertised surface
stays honest - see :mod:`mcp_radia.tools.genesys`.

To implement
------------
Enable Swagger in *AdminTools -> Configure REST API* on the instance, read the
real contract from its Swagger UI, then build the client against it. The data
model to expect: a **project** is a model repository; an **entity** is the unit
of content (Requirement, Component, Function, Interface, ...) with free-form
**attributes** and typed **relationships** to other entities. Those
relationships are the native traceability records the linking layer wants.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_radia.config import ENV_FILE
from mcp_radia.connectors.errors import ConnectorNotImplementedError

SYSTEM = "genesys"

_NOT_IMPLEMENTED = (
    "The GENESYS connector is a placeholder and has no implementation yet. Its REST "
    "contract could not be verified from public documentation; confirm it against the "
    "instance's Swagger UI (AdminTools -> Configure REST API) and implement "
    "mcp_radia/connectors/genesys.py."
)


class GenesysSettings(BaseSettings):
    """Vitech GENESYS connection settings, read from ``GENESYS_*`` variables.

    Parsed today so configuration can be staged ahead of the implementation.
    Nothing reads these yet.
    """

    model_config = SettingsConfigDict(env_prefix="GENESYS_", env_file=ENV_FILE, extra="ignore")

    base_url: str = Field(
        default="",
        description="GENESYS server root, e.g. https://genesys.internal:8443 (no API path).",
    )
    api_base_path: str = Field(
        default="api/v1",
        description="Path segment the REST API is mounted at, without leading or trailing slash.",
    )
    grant_type: Literal["password", "client_credentials"] = Field(
        default="password", description="OAuth grant to use once implemented."
    )
    username: str = Field(default="", description="GENESYS user (password grant).")
    password: str = Field(default="", description="GENESYS password (password grant).")
    client_id: str = Field(default="", description="OAuth client id, if the instance needs one.")
    client_secret: str = Field(default="", description="OAuth client secret.")
    timeout_seconds: float = Field(default=30.0, gt=0, description="Per-request timeout.")
    verify_ssl: bool = Field(
        default=True,
        description="Verify TLS certificates. Often disabled for on-prem self-signed certs.",
    )

    @property
    def api_base(self) -> str:
        """Fully-qualified API base, e.g. ``https://host:8443/api/v1``."""
        return f"{self.base_url.rstrip('/')}/{self.api_base_path.strip('/')}"

    @property
    def is_configured(self) -> bool:
        """Whether credentials are staged. Does not imply the connector works."""
        if not self.base_url:
            return False
        if self.grant_type == "client_credentials":
            return bool(self.client_id and self.client_secret)
        return bool(self.username and self.password)


class GenesysRelationship(BaseModel):
    """A typed link from one entity to another. Intended shape; not yet produced."""

    relation: str = Field(description="Relationship name, e.g. 'refines' or 'specifies'.")
    target_id: str = Field(default="", description="Id of the entity on the other end.")
    target_name: str = Field(default="", description="Name of the target entity.")
    target_class: str | None = Field(default=None, description="Class of the target entity.")


class GenesysEntity(BaseModel):
    """A GENESYS entity. Intended shape; not yet produced."""

    id: str = Field(description="Entity id.")
    name: str = Field(default="", description="Entity name.")
    number: str | None = Field(default=None, description="Entity number, e.g. R.1.2.")
    entity_class: str | None = Field(
        default=None, description="GENESYS class, e.g. Requirement, Component, Function."
    )
    project_id: str | None = Field(default=None, description="Id of the owning project.")
    description: str = Field(default="", description="Description, flattened to plain text.")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Full attribute map.")
    relationships: list[GenesysRelationship] = Field(
        default_factory=list, description="Typed links to other entities."
    )


class GenesysClient:
    """Placeholder client. Every operation raises :class:`ConnectorNotImplementedError`."""

    def __init__(self, settings: GenesysSettings) -> None:
        self._settings = settings

    @property
    def settings(self) -> GenesysSettings:
        return self._settings

    @property
    def is_implemented(self) -> bool:
        """Always False. The linking layer checks this before dispatching."""
        return False

    @property
    def is_configured(self) -> bool:
        """Credentials staged, which is not the same as usable."""
        return self._settings.is_configured

    def _unimplemented(self) -> ConnectorNotImplementedError:
        return ConnectorNotImplementedError(_NOT_IMPLEMENTED, system=SYSTEM)

    async def list_projects(self) -> list[object]:
        """Not implemented."""
        raise self._unimplemented()

    async def get_entity(self, project_id: str, entity_id: str) -> GenesysEntity:
        """Not implemented."""
        raise self._unimplemented()

    async def search_entities(self, *, project_id: str) -> list[GenesysEntity]:
        """Not implemented."""
        raise self._unimplemented()

    async def aclose(self) -> None:
        """No HTTP client is held, so there is nothing to close."""
        return
