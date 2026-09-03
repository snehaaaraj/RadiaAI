"""
Document extraction utilities for the ingestion pipeline.

Extracts plain text from common document formats (PDF, plain text, Markdown).
Falls back to raw UTF-8 decoding for unsupported formats.
"""

from __future__ import annotations

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
    """Extract per-page text from a PDF using PyMuPDF (fitz) if available, else basic fallback."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=data, filetype="pdf")
        pages = [(i + 1, page.get_text()) for i, page in enumerate(doc)]
        doc.close()
        return pages
    except ImportError:
        logger.warning("pymupdf_not_installed_using_fallback")
        # Very basic PDF text extraction fallback — page boundaries are unknown,
        # so the whole document is reported as a single unnumbered page.
        text = data.decode("latin-1", errors="replace")
        # Strip binary noise — not reliable but better than nothing
        import re

        clean = re.sub(r"[^\x20-\x7E\n\r\t]", " ", text)
        return [(1, clean)]
