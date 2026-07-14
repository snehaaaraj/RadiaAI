"""Chat endpoint schemas — request/response models for the RAG chat interface."""

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in a conversation turn."""

    role: str = Field(description="'user' or 'assistant'")
    content: str = Field(min_length=1, description="Message content")


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


class CitedChunk(BaseModel):
    """A document chunk used as evidence in the answer."""

    chunk_id: str
    source: str
    filename: str
    section: str = ""
    page_number: int | None = None
    score: float
    content_snippet: str = Field(description="First 300 chars of chunk content")


class ChatResponse(BaseModel):
    """Response body for POST /api/v1/chat."""

    answer: str = Field(description="LLM-generated answer grounded in retrieved chunks")
    citations: list[CitedChunk] = Field(
        default_factory=list,
        description="Source chunks used to produce the answer",
    )
    model: str = Field(description="Azure OpenAI deployment used for generation")
    retrieval_count: int = Field(description="Number of chunks retrieved")
