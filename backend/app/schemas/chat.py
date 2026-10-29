"""Chat endpoint schemas - request/response models for the RAG chat interface."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in a conversation turn."""

    # Restricted to a Literal (rather than a free-form str) so a caller cannot
    # smuggle a "system" role turn into conversation_history and have it
    # forwarded to the LLM as an extra system message - that would let an
    # attacker inject instructions with system-level priority.
    role: Literal["user", "assistant"] = Field(description="'user' or 'assistant'")
    content: str = Field(min_length=1, max_length=4000, description="Message content")


class ChatRequest(BaseModel):
    """Request body for POST /api/v1/chat."""

    question: str = Field(
        min_length=1,
        max_length=4000,
        description="The user's question to answer from the indexed documents",
    )
    conversation_history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=20,
        description="Prior conversation turns for multi-turn context",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of document chunks to retrieve",
    )
    citation_style: Literal["inline", "none"] = Field(
        default="inline",
        description=(
            "'inline' cites source filenames in parentheses within the answer text "
            "(used by the full chat page). 'none' omits filenames from the answer "
            "text entirely (used by the compact chat widget). The structured "
            "'citations' array is always returned regardless of this setting."
        ),
    )
    mode: Literal["standards", "radiaai"] = Field(
        default="standards",
        description=(
            "'standards' (default) answers from the indexed standards documents only - "
            "no live-data tools. 'radiaai' (entered in the UI with '/radiaai', left with "
            "'/exit') skips document retrieval and answers only from mcp-radia live "
            "engineering-data tools (e.g. Jama)."
        ),
    )


class CitedChunk(BaseModel):
    """A document chunk used as evidence in the answer."""

    chunk_id: str
    source: str
    filename: str
    section: str = ""
    page_number: int | None = None
    score: float
    content_snippet: str = Field(description="First 300 chars of chunk content")


class ChatSource(BaseModel):
    """A live-data source (e.g. a Jama item) used to ground part of the answer."""

    label: str = Field(description="Human-readable identifier, e.g. a Jama document key")
    url: str = Field(description="Validated https URL to the source item")


class ChatResponse(BaseModel):
    """Response body for POST /api/v1/chat."""

    answer: str = Field(description="LLM-generated answer grounded in retrieved chunks")
    citations: list[CitedChunk] = Field(
        default_factory=list,
        description="Source chunks used to produce the answer",
    )
    model: str = Field(description="Azure OpenAI deployment used for generation")
    retrieval_count: int = Field(description="Number of chunks retrieved")
    used_mcp: bool = Field(
        default=False,
        description="True when the answer used a live engineering-data tool call (e.g. Jama)",
    )
    sources: list[ChatSource] = Field(
        default_factory=list,
        description="Live-data sources used to ground the answer, when used_mcp is true",
    )
