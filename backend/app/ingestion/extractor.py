"""
Document extraction utilities for the ingestion pipeline.

Extracts plain text from the formats accepted by ingestion.
"""

from __future__ import annotations

import io

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
    if lower.endswith(".docx"):
        return [(1, _extract_docx(data))]
    if lower.endswith((".txt", ".md", ".csv", ".json", ".xml")):
        return [(1, data.decode("utf-8"))]
    raise ValueError(f"Unsupported document type: {filename}")


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


def _extract_docx(data: bytes) -> str:
    """Extract paragraph text from a validated DOCX document."""
    try:
        from docx import Document
    except ImportError as exc:
        raise ConfigurationError(
            "python-docx is required to extract DOCX documents",
            detail={"dependency": "python-docx"},
        ) from exc
    document = Document(io.BytesIO(data))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)
