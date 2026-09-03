"""
Document chunking for the ingestion pipeline.

Splits document text into overlapping chunks suitable for embedding and
indexing into Azure AI Search. Uses a simple token-approximate approach
based on whitespace splitting (avoids a tokenizer dependency).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

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
    context across chunk boundaries. Chunks produced this way have no page
    number — use ``chunk_pages`` when the document's page boundaries are
    known so findings can be traced back to a specific page.
    """
    return chunk_pages(
        [(None, text)],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        source=source,
        filename=filename,
        document_type=document_type,
        file_hash=file_hash,
    )


def chunk_pages(
    pages: list[tuple[int | None, str]],
    *,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    source: str = "",
    filename: str = "",
    document_type: str = "",
    file_hash: str = "",
) -> list[Chunk]:
    """
    Split paginated document text into overlapping chunks, one page at a time.

    *pages* is a list of ``(page_number, text)`` pairs, e.g. from
    ``extract_pages``. Chunking per page (rather than across the whole
    document) means every chunk can carry an accurate ``page_number``, which
    is required to trace an AI review finding back to the exact page of the
    source-of-truth document that produced it. The tradeoff is that overlap
    context is not carried across a page boundary — acceptable since a page
    break is itself a natural place to split.
    """
    chunks: list[Chunk] = []
    idx = 0
    total_words = 0

    for page_number, text in pages:
        if not text or not text.strip():
            continue

        words = text.split()
        total_words += len(words)
        if not words:
            continue

        start = 0
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
                    page_number=page_number,
                    file_hash=file_hash,
                )
            )
            idx += 1

            if end >= len(words):
                break
            start = end - chunk_overlap

    logger.info(
        "text_chunked", filename=filename, total_chunks=len(chunks), total_words=total_words
    )
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
