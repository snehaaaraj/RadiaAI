"""Unit tests for document text extraction."""

from __future__ import annotations

import sys

import fitz
import pytest

from app.core.exceptions import ConfigurationError
from app.ingestion.extractor import extract_pages


@pytest.mark.unit
def test_pdf_extraction_preserves_acronym_definition() -> None:
    """Text embedded in an acronym PDF remains searchable after extraction."""
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "AMMP")
    page.insert_text((72, 96), "Aircraft Maturity Management Plan")
    data = document.tobytes()
    document.close()

    pages = extract_pages(data, "acronyms.pdf")

    assert pages == [(1, "AMMP\nAircraft Maturity Management Plan\n")]


@pytest.mark.unit
def test_pdf_extraction_fails_when_pymupdf_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing PDF support is explicit and never indexes decoded binary noise."""
    monkeypatch.setitem(sys.modules, "fitz", None)

    with pytest.raises(ConfigurationError, match="PyMuPDF is required"):
        extract_pages(b"%PDF-binary-data", "acronyms.pdf")
