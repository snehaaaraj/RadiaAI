"""Document management schemas."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

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


class DocumentChunk(BaseModel):
    """A single indexed chunk belonging to a document."""

    chunk_id: str
    content: str
    chunk_index: int
    page_number: int | None = None
    section: str = ""


class DocumentDetail(DocumentSummary):
    """Document-level metadata with all indexed chunks."""

    chunks: list[DocumentChunk] = Field(default_factory=list)


class DocumentDeleteResponse(BaseModel):
    """Confirmation that an indexed document was removed."""

    document_id: str
    message: str


class IngestRequest(BaseModel):
    """Request body for triggering ingestion of already-uploaded documents."""

    source: Literal["blob", "sharepoint"] = Field(description="Connector source identifier")
    document_ids: list[str] = Field(
        default_factory=list,
        max_length=500,
        description="Subset to ingest; empty = all",
    )


class IngestResponse(BaseModel):
    """Response body for ingest requests."""

    job_id: str = Field(description="Background job ID to poll for status")
    queued_count: int
    message: str


class IngestionStatusResponse(BaseModel):
    """Response body describing the most recent ingestion run, if any."""

    timestamp: datetime | None = Field(
        default=None, description="When the most recent ingestion run completed"
    )
    source: str | None = Field(default=None, description="'sharepoint' or 'blob'")
    trigger: str | None = Field(default=None, description="'manual' or 'webhook'")
    outcome: str | None = Field(default=None, description="'success' or 'error'")
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    message: str = ""


class IngestionJobResponse(BaseModel):
    """Durable status of one queued ingestion job."""

    job_id: str
    source: str
    trigger: Literal["manual", "webhook"]
    status: Literal["queued", "processing", "retrying", "completed", "failed"]
    created_at: datetime
    updated_at: datetime
    attempt: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    message: str = ""
    failure_details: list[dict[str, str]] = Field(default_factory=list)
