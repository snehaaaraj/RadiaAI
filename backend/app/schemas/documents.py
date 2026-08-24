"""Document management schemas."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class DocumentMetadata(BaseModel):
    """Metadata preserved for every ingested document."""

    source: str = Field(description="Origin system (e.g. 'folder', 'jama', 'sharepoint')")
    filename: str
    document_type: str = ""
    author: str = ""
    version: str = ""
    modified_date: datetime | None = None


class DocumentSummary(BaseModel):
    """Lightweight representation of a document for list responses."""

    document_id: str
    filename: str
    status: DocumentStatus
    chunk_count: int = 0
    metadata: DocumentMetadata
    ingested_at: datetime | None = None


class IngestRequest(BaseModel):
    """Request body for triggering ingestion of already-uploaded documents."""

    source: str = Field(description="Connector source identifier")
    document_ids: list[str] = Field(
        default_factory=list, description="Subset to ingest; empty = all"
    )


class IngestResponse(BaseModel):
    """Response body for ingest requests."""

    job_id: str = Field(description="Background job ID to poll for status")
    queued_count: int
    message: str
