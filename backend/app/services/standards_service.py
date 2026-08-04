"""Service layer for standards catalog endpoints."""

from app.connectors.sharepoint_client import SharePointStandardsClient
from app.core.logging import get_logger
from app.models.standards_models import StandardsResponse
from app.standards.registry import StandardsRegistry

logger = get_logger(__name__)


class StandardsService:
    """
    Returns standards metadata for the review engine.

    Priority:
      1. SharePoint — live document listing from the configured folder.
      2. Registry   — hardcoded fallback used when SharePoint is not
                      configured or unavailable.
    """

    def __init__(
        self,
        registry: StandardsRegistry,
        sharepoint_client: SharePointStandardsClient | None = None,
    ) -> None:
        self._registry = registry
        self._sharepoint = sharepoint_client

    def list_standards(self) -> StandardsResponse:
        # Try SharePoint first
        if self._sharepoint is not None and self._sharepoint._settings.is_configured:
            standards = self._sharepoint.fetch_standards()
            if standards:
                return StandardsResponse(standards=standards, source="sharepoint")
            # fetch_standards already logged the failure — fall through
            logger.warning("sharepoint_returned_empty_falling_back_to_registry")

        # Fallback: hardcoded registry
        return StandardsResponse(
            standards=self._registry.list_standards(),
            source="registry",
        )

