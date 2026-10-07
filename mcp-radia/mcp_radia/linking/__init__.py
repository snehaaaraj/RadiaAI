"""Cross-system linking: tracing one item to related items in other systems.

Queries every connector live on each call - there is no link datastore. See
:mod:`mcp_radia.linking.service` for what that buys and what it costs.
"""

from mcp_radia.linking.models import RelatedItem, RelatedItemsResult
from mcp_radia.linking.service import MAX_TEXT_LOOKUPS, LinkingService

__all__ = [
    "MAX_TEXT_LOOKUPS",
    "LinkingService",
    "RelatedItem",
    "RelatedItemsResult",
]
