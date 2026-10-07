"""Models for cross-system linking."""

from typing import Literal

from pydantic import BaseModel, Field

#: Systems the linking layer can be asked about. GENESYS is accepted so the
#: answer can be "not implemented yet" rather than "unknown system".
LinkableSystem = Literal["jama", "jira", "confluence", "genesys"]

#: How a relationship was found. ``native`` means the source system records it
#: as a first-class link. ``text`` means we spotted an identifier in prose and
#: resolved it - useful, but a heuristic.
DiscoveredVia = Literal["native", "text"]


class RelatedItem(BaseModel):
    """One item related to the item that was asked about."""

    system: str = Field(
        description=(
            "System the related item lives in: jama, jira, confluence, or 'unresolved' "
            "for a text reference that matched nothing."
        )
    )
    id: str | None = Field(
        default=None, description="Native id, usable with that system's get tool."
    )
    key: str | None = Field(
        default=None,
        description="Human-readable key, e.g. BMS-451 or SRS-42, when the system has one.",
    )
    title: str = Field(default="", description="Name or summary of the related item.")
    relation: str = Field(
        description=(
            "How it relates, in the source system's own words where possible: 'blocks', "
            "'upstream', 'parent', 'links-to', or 'text-reference'."
        )
    )
    discovered_via: DiscoveredVia = Field(
        description="'native' for a first-class link, 'text' for an identifier found in prose."
    )
    web_url: str | None = Field(default=None, description="Browser URL for a human to open.")


class RelatedItemsResult(BaseModel):
    """Everything related to one item, across systems."""

    system: str = Field(description="System the queried item lives in.")
    item_id: str = Field(description="Id that was queried.")
    item_title: str = Field(default="", description="Name or summary of the queried item.")
    related: list[RelatedItem] = Field(
        default_factory=list, description="Related items, native links first."
    )
    notes: list[str] = Field(
        default_factory=list,
        description=(
            "Anything that limited the answer: a connector not configured, a system not "
            "implemented, or a truncated text scan. Read these before treating the list "
            "as complete."
        ),
    )
