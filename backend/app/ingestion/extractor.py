"""
Document extraction utilities for the ingestion pipeline.

Extracts plain text from common document formats (PDF, DOCX, plain text, Markdown).
Falls back to raw UTF-8 decoding for unsupported formats.
"""

from __future__ import annotations

import io

from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_text(data: bytes, filename: str) -> str:
    """Extract plain text from a document based on its file extension."""
    lower = filename.lower()

    if lower.endswith(".pdf"):
        return _extract_pdf(data)
    if lower.endswith((".docx",)):
        return _extract_docx(data)
    if lower.endswith((".txt", ".md", ".csv", ".json", ".xml")):
        return data.decode("utf-8", errors="replace")

    # Fallback: try UTF-8 decode
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        logger.warning("text_extraction_fallback_failed", filename=filename)
        return ""


def _extract_pdf(data: bytes) -> str:
    """Extract text from a PDF using PyMuPDF (fitz) if available, else basic fallback."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(stream=data, filetype="pdf")
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n\n".join(pages)
    except ImportError:
        logger.warning("pymupdf_not_installed_using_fallback")
        # Very basic PDF text extraction fallback
        text = data.decode("latin-1", errors="replace")
        # Strip binary noise — not reliable but better than nothing
        import re
        clean = re.sub(r"[^\x20-\x7E\n\r\t]", " ", text)
        return clean


def _extract_docx(data: bytes) -> str:
    """Extract text from a DOCX file."""
    try:
        from docx import Document  # python-docx

        doc = Document(io.BytesIO(data))
        return "\n\n".join(para.text for para in doc.paragraphs if para.text.strip())
    except ImportError:
        logger.warning("python_docx_not_installed")
        return data.decode("utf-8", errors="replace")
