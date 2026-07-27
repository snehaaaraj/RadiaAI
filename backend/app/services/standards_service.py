"""Service layer for standards catalog endpoints."""

from app.models.standards_models import StandardsResponse
from app.standards.registry import StandardsRegistry


class StandardsService:
    """Returns deterministic standards metadata used by review engines."""

    def __init__(self, registry: StandardsRegistry) -> None:
        self._registry = registry

    def list_standards(self) -> StandardsResponse:
        return StandardsResponse(standards=self._registry.list_standards())

