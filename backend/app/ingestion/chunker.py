"""
Document chunking for the ingestion pipeline.

Splits document text into overlapping chunks suitable for embedding and
indexing into Azure AI Search. Uses a simple token-approximate approach
based on whitespace splitting (avoids a tokenizer dependency).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Chunk:
    """A single text chunk with provenance metadata."""

    chunk_id: str
    content: str
    chunk_index: int
    source: str = ""
    filename: str = ""
    document_type: str = ""
    section: str = ""
    page_number: int | None = None
    file_hash: str = ""


def chunk_text(
    text: str,
    *,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    source: str = "",
    filename: str = "",
    document_type: str = "",
    file_hash: str = "",
) -> list[Chunk]:
    """
    Split *text* into overlapping chunks of approximately *chunk_size* words.

    Each chunk overlaps with the next by *chunk_overlap* words to preserve
    context across chunk boundaries.
    """
    if not text or not text.strip():
        return []

    # Normalize whitespace
    words = text.split()
    if not words:
        return []

    chunks: list[Chunk] = []
    start = 0
    idx = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        content = " ".join(chunk_words)

        # Detect section headers (lines starting with a number or all-caps)
        section = _detect_section(content)

        chunk_id = _make_chunk_id(filename, file_hash, idx)
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                content=content,
                chunk_index=idx,
                source=source,
                filename=filename,
                document_type=document_type,
                section=section,
                file_hash=file_hash,
            )
        )
        idx += 1

        if end >= len(words):
            break
        start = end - chunk_overlap

    logger.info("text_chunked", filename=filename, total_chunks=len(chunks), total_words=len(words))
    return chunks


def _detect_section(text: str) -> str:
    """Try to extract a section heading from the first line of a chunk."""
    first_line = text.split("\n")[0].strip()[:120]
    # Match patterns like "1.2.3 Section Title" or "APPENDIX A"
    match = re.match(r"^(\d+[\.\d]*\s+.+|[A-Z]{3,}.*)$", first_line)
    return match.group(0) if match else ""


def _make_chunk_id(filename: str, file_hash: str, chunk_index: int) -> str:
    """Generate a deterministic chunk ID."""
    raw = f"{filename}:{file_hash}:{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]
