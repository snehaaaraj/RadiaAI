"""Focused tests for durable ingestion, upload validation, and queue retries."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from azure.core.exceptions import ResourceExistsError
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

import app.ingestion.job_store as job_store_module
import app.ingestion.worker as worker_module
from app.ingestion.job_store import IdempotencyConflictError, IngestionJobStore
from app.ingestion.validation import read_validated_upload, validate_document
from app.ingestion.worker import process_ingestion_job


@pytest.mark.unit
def test_document_validation_accepts_text_and_rejects_bad_mime() -> None:
    assert validate_document(b"valid document", "spec.txt", "text/plain") == "spec.txt"

    with pytest.raises(HTTPException) as exc_info:
        validate_document(b"valid document", "spec.txt", "application/pdf")

    assert exc_info.value.status_code == 415


@pytest.mark.unit
def test_document_validation_rejects_path_traversal_and_corrupt_pdf() -> None:
    with pytest.raises(HTTPException) as traversal:
        validate_document(b"text", "../spec.txt", "text/plain")
    assert traversal.value.status_code == 422

    with pytest.raises(HTTPException) as corrupt_pdf:
        validate_document(b"%PDF-not-a-document", "spec.pdf", "application/pdf")
    assert corrupt_pdf.value.status_code == 422


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upload_reader_enforces_limit_before_accepting_file() -> None:
    file = UploadFile(
        filename="spec.txt",
        file=io.BytesIO(b"12345"),
        headers=Headers({"content-type": "text/plain"}),
    )

    with pytest.raises(HTTPException) as exc_info:
        await read_validated_upload(file, max_bytes=4)

    assert exc_info.value.status_code == 413


class _MemoryBlob:
    def __init__(self, container: _MemoryContainer, name: str) -> None:
        self.container = container
        self.name = name

    def upload_blob(self, data: bytes, *, overwrite: bool = False, **_: Any) -> None:
        if not overwrite and self.name in self.container.data:
            raise ResourceExistsError("already exists")
        self.container.data[self.name] = data

    def download_blob(self) -> _MemoryDownload:
        return _MemoryDownload(self.container.data[self.name])


class _MemoryDownload:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def readall(self) -> bytes:
        return self.data


class _MemoryContainer:
    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    def get_blob_client(self, name: str) -> _MemoryBlob:
        return _MemoryBlob(self, name)

    def get_container_properties(self) -> None:
        return None

    def list_blobs(self, *, name_starts_with: str) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(name=name)
            for name in self.data
            if name.startswith(name_starts_with) and name.endswith(".json")
        ]


class _MemoryBlobService:
    container = _MemoryContainer()

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    @classmethod
    def from_connection_string(cls, *_: Any, **__: Any) -> _MemoryBlobService:
        return cls()

    def get_container_client(self, _: str) -> _MemoryContainer:
        return self.container


class _MemoryQueue:
    messages: list[str] = []

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    @classmethod
    def from_connection_string(cls, *_: Any, **__: Any) -> _MemoryQueue:
        return cls()

    def create_queue(self) -> None:
        return None

    def send_message(self, message: str) -> None:
        self.messages.append(message)


@pytest.mark.unit
def test_queue_store_stages_upload_and_enforces_idempotency(
    monkeypatch: pytest.MonkeyPatch, test_settings
) -> None:
    _MemoryBlobService.container = _MemoryContainer()
    _MemoryQueue.messages = []
    monkeypatch.setattr(job_store_module, "BlobServiceClient", _MemoryBlobService)
    monkeypatch.setattr(job_store_module, "QueueClient", _MemoryQueue)
    store = IngestionJobStore(test_settings)

    job, created = store.enqueue(
        source="upload",
        trigger="manual",
        upload=(b"the document", "spec.txt", "text/plain"),
        idempotency_key="request-1",
    )
    duplicate, duplicate_created = store.enqueue(
        source="upload",
        trigger="manual",
        upload=(b"the document", "spec.txt", "text/plain"),
        idempotency_key="request-1",
    )

    assert created is True
    assert duplicate_created is False
    assert duplicate["job_id"] == job["job_id"]
    assert store.get_upload(job) == b"the document"
    assert len(_MemoryQueue.messages) == 1

    job_blob = f"system/ingestion-jobs/{job['job_id']}.json"
    record = json.loads(_MemoryBlobService.container.data[job_blob])
    record["created_at"] = (datetime.now(UTC) - timedelta(minutes=3)).isoformat()
    record["queue_submitted_at"] = None
    _MemoryBlobService.container.data[job_blob] = json.dumps(record).encode()
    assert store.redispatch_unsubmitted(older_than=timedelta(minutes=2)) == 1
    assert len(_MemoryQueue.messages) == 2

    with pytest.raises(IdempotencyConflictError):
        store.enqueue(
            source="upload",
            trigger="manual",
            upload=(b"different content", "spec.txt", "text/plain"),
            idempotency_key="request-1",
        )


class _MemoryJobStore:
    def __init__(self, job: dict[str, Any]) -> None:
        self.job = job

    def get(self, _: str) -> dict[str, Any]:
        return self.job.copy()

    def update(self, _: str, **fields: Any) -> dict[str, Any]:
        self.job.update(fields)
        return self.job.copy()


class _FailingIngestion:
    def ingest_from_blob(self, document_ids: list[str] | None = None) -> dict[str, Any]:
        raise RuntimeError("transient search failure")


@pytest.mark.unit
def test_worker_persists_retrying_state_before_queue_redelivery(
    monkeypatch: pytest.MonkeyPatch, test_settings
) -> None:
    job = {
        "job_id": "job-1",
        "status": "queued",
        "source": "blob",
        "trigger": "manual",
        "upload_blob": None,
        "document_ids": [],
        "failed": 0,
    }
    store = _MemoryJobStore(job)
    monkeypatch.setattr(worker_module, "build_ingestion_service", lambda _: _FailingIngestion())

    with pytest.raises(RuntimeError, match="transient search failure"):
        process_ingestion_job("job-1", dequeue_count=1, settings=test_settings, job_store=store)

    assert store.job["status"] == "retrying"
    assert store.job["attempt"] == 1
    assert store.job["failure_details"][0]["error"] == "transient search failure"
