"""Service layer for standards catalog endpoints."""

from app.connectors.sharepoint_client import SharePointStandardsClient
from app.core.logging import get_logger
from app.models.standards_models import StandardReference, StandardsResponse
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

    def resolve_reference(
        self,
        reference_text: str,
        *,
        category: str | None = None,
        reviewer: str | None = None,
    ) -> StandardReference | None:
        """
        Resolve a reviewer reference label to the most relevant standards document.

        The returned reference is used to hyperlink findings back to the originating
        SharePoint file when available.
        """
        standards = self.list_standards().standards
        if not standards:
            return None

        normalized = _normalize(reference_text)
        category_hint = _normalize(category or "")
        reviewer_hint = _normalize(reviewer or "")

        aliases = _reference_aliases(normalized, category_hint, reviewer_hint)

        best_standard: StandardReference | None = None
        best_score = -1
        for standard in standards:
            score = _score_standard(standard, aliases)
            if score > best_score:
                best_score = score
                best_standard = standard

        return best_standard if best_score > 0 else None


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())


def _reference_aliases(reference_text: str, category: str, reviewer: str) -> set[str]:
    aliases = {reference_text, category, reviewer}
    tokens = set(reference_text.split()) | set(category.split()) | set(reviewer.split())

    if "incose" in tokens or "incose" in reference_text:
        aliases.update({"incose", "systems engineering", "requirements"})
    if "ears" in tokens or "ears" in reference_text:
        aliases.update({"ears", "requirement syntax"})
    if "style" in tokens or "guide" in tokens:
        aliases.update({"style guide", "company style guide", "engineering standards",
                         "company-style-guide"})
    if "internal" in tokens or "engineering" in tokens:
        aliases.update({"company-style-guide", "style guide", "engineering standards"})
    if "traceability" in tokens or "trace" in tokens:
        aliases.update({"traceability", "trace guide"})
    if "verification" in tokens or "verifiability" in tokens:
        aliases.update({"verification", "verifiability", "test", "analysis"})
    if "certification" in tokens or "cert" in tokens:
        aliases.update({"certification", "cert", "approval", "cert-guidance"})

    return {alias for alias in aliases if alias}


def _score_standard(standard: StandardReference, aliases: set[str]) -> int:
    # Exact key match — highest priority, prevents cross-standard bleed
    normalized_aliases = {_normalize(a) for a in aliases}
    if _normalize(standard.key) in normalized_aliases:
        return 100

    searchable = " ".join(
        [
            standard.key,
            standard.name,
            standard.source,
            standard.description,
            " ".join(standard.categories),
        ]
    ).lower()

    score = 0
    for alias in aliases:
        if alias in searchable:
            score += 3

    # Prefer documents whose categories line up with the reviewer intent.
    category_hits = sum(1 for category in standard.categories if category in aliases)
    score += category_hits * 2

    return score
