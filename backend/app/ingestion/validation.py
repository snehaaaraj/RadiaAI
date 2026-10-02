"""Validation for documents accepted by the ingestion pipeline."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import PurePath

from defusedxml import ElementTree as ET
from fastapi import HTTPException, UploadFile, status

_MIME_TYPES = {
    ".csv": {"text/csv", "application/csv", "application/octet-stream"},
    ".json": {"application/json", "text/json", "application/octet-stream"},
    ".md": {"text/markdown", "text/plain", "application/octet-stream"},
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".xml": {"application/xml", "text/xml", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
}
SUPPORTED_EXTENSIONS = frozenset(_MIME_TYPES)


def validate_document(
    data: bytes,
    filename: str,
    content_type: str,
    *,
    allow_paths: bool = False,
) -> str:
    """Validate filename, declared MIME, and file content before ingestion."""
    normalized_name = filename.replace("\\", "/")
    path_parts = normalized_name.split("/")
    if (
        not normalized_name
        or any(part in {"", ".", ".."} for part in path_parts)
        or (not allow_paths and len(path_parts) != 1)
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid filename.")
    safe_name = PurePath(normalized_name).name
    extension = PurePath(safe_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported file extension.")
    mime = content_type.partition(";")[0].strip().lower()
    if mime and mime not in _MIME_TYPES[extension]:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "MIME type does not match file."
        )
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The uploaded file is empty.")

    try:
        if extension == ".pdf":
            if not data.startswith(b"%PDF-"):
                raise ValueError("Invalid PDF signature.")
            import fitz

            with fitz.open(stream=data, filetype="pdf") as document:
                if document.page_count == 0:
                    raise ValueError("PDF contains no pages.")
        elif extension == ".docx":
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise ValueError("Invalid DOCX document.")
                ET.fromstring(archive.read("word/document.xml"))
        else:
            text = data.decode("utf-8")
            if not text.strip() or "\x00" in text:
                raise ValueError("File does not contain valid text.")
            if extension == ".json":
                json.loads(text)
            elif extension == ".xml":
                ET.fromstring(text)
            elif extension == ".csv" and not next(csv.reader(io.StringIO(text)), None):
                raise ValueError("CSV contains no rows.")
    except (ValueError, UnicodeDecodeError, zipfile.BadZipFile, ET.ParseError, csv.Error) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "File content is invalid or corrupted."
        ) from exc
    except ImportError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "PDF validation dependency is unavailable."
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "File content is invalid or corrupted."
        ) from exc
    return normalized_name if allow_paths else safe_name


async def read_validated_upload(file: UploadFile, *, max_bytes: int) -> tuple[bytes, str]:
    """Read an upload in bounded chunks, rejecting it before buffering beyond the cap."""
    filename = file.filename or ""
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(min(64 * 1024, max_bytes + 1 - size)):
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds upload limit."
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    safe_name = validate_document(data, filename, file.content_type or "")
    return data, safe_name
