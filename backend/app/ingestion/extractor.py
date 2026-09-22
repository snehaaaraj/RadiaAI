"""
Document extraction utilities for the ingestion pipeline.

Extracts plain text from common document formats (PDF, plain text, Markdown).
Falls back to raw UTF-8 decoding for unsupported non-PDF formats.
"""

from __future__ import annotations

from app.core.exceptions import ConfigurationError
from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_text(data: bytes, filename: str) -> str:
    """Extract plain text from a document based on its file extension."""
    return "\n\n".join(text for _page_number, text in extract_pages(data, filename))


def extract_pages(data: bytes, filename: str) -> list[tuple[int, str]]:
    """
    Extract plain text from a document, keeping page boundaries.

    Returns a list of ``(page_number, text)`` pairs, 1-indexed. Formats without a
    native concept of pages (plain text, Markdown, etc.) are returned as a
    single page numbered 1, so callers can treat every document uniformly
    without special-casing non-paginated formats.
    """
    lower = filename.lower()

    if lower.endswith(".pdf"):
        return _extract_pdf_pages(data)
    if lower.endswith((".txt", ".md", ".csv", ".json", ".xml")):
        return [(1, data.decode("utf-8", errors="replace"))]

    # Fallback: try UTF-8 decode
    try:
        return [(1, data.decode("utf-8", errors="replace"))]
    except Exception:
        logger.warning("text_extraction_fallback_failed", filename=filename)
        return [(1, "")]


def _extract_pdf_pages(data: bytes) -> list[tuple[int, str]]:
    """Extract per-page text from a PDF using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise ConfigurationError(
            "PyMuPDF is required to extract PDF documents",
            detail={"dependency": "PyMuPDF"},
        ) from exc

    with fitz.open(stream=data, filetype="pdf") as doc:
        return [(i + 1, page.get_text()) for i, page in enumerate(doc)]
