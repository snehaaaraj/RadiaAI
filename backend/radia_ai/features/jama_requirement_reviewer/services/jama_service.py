"""Service layer for the Jama Connect integration.

Wraps :class:`JamaClient` so endpoints depend on a small, testable surface and
so future concerns (caching, per-user tokens, field mapping) have a home that
does not leak into the transport client.
"""

from app.core.logging import get_logger
from radia_ai.features.jama_requirement_reviewer.connectors.jama_client import JamaClient
from radia_ai.features.jama_requirement_reviewer.models.jama_models import (
    JamaProjectList,
    JamaRequirement,
    JamaRequirementSearchResult,
)

logger = get_logger(__name__)


class JamaService:
    """Read operations for Jama projects and requirements."""

    def __init__(self, client: JamaClient) -> None:
        self._client = client

    @property
    def is_configured(self) -> bool:
        return self._client.is_configured

    def list_projects(self) -> JamaProjectList:
        projects = self._client.list_projects()
        logger.info("jama_projects_listed", count=len(projects))
        return JamaProjectList(projects=projects)

    def search_requirements(
        self,
        *,
        project_id: int | None = None,
        contains: str | None = None,
        item_type_id: int | None = None,
        start_at: int = 0,
        max_results: int = 50,
    ) -> JamaRequirementSearchResult:
        result = self._client.search_requirements(
            project_id=project_id,
            contains=contains,
            item_type_id=item_type_id,
            start_at=start_at,
            max_results=max_results,
        )
        logger.info(
            "jama_requirements_searched",
            project_id=project_id,
            returned=len(result.results),
            total=result.total,
        )
        return result

    def get_requirement(self, item_id: int) -> JamaRequirement:
        requirement = self._client.get_requirement(item_id)
        logger.info("jama_requirement_read", item_id=item_id, document_key=requirement.document_key)
        return requirement
