"""Search endpoint schemas."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SearchMode(StrEnum):
    KEYWORD = "keyword"
    VECTOR = "vector"
    HYBRID = "hybrid"


class SearchRequest(BaseModel):
    """Request body for POST /api/v1/search."""

    query: str = Field(min_length=1, max_length=1000)
    mode: SearchMode = Field(default=SearchMode.HYBRID)
    top_k: int = Field(default=10, ge=1, le=50)
    filters: dict[str, Any] = Field(default_factory=dict, description="Metadata filters for search")


class SearchResult(BaseModel):
    """A single search result."""

    chunk_id: str
    score: float
    source: str
    filename: str
    document_type: str = ""
    section: str = ""
    page_number: int | None = None
    content: str
    highlights: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Response body for POST /api/v1/search."""

    results: list[SearchResult]
    total: int
    mode: SearchMode
