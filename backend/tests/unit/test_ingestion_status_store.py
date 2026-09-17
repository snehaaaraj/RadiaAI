"""Unit tests for the ingestion status store."""

from __future__ import annotations

import pytest
from tests.conftest import InMemoryBlobClient

from app.ingestion.status_store import IngestionStatusStore


@pytest.mark.unit
def test_get_latest_returns_none_when_no_status_recorded() -> None:
    store = IngestionStatusStore(InMemoryBlobClient())

    assert store.get_latest() is None


@pytest.mark.unit
def test_record_and_get_latest_roundtrip() -> None:
    store = IngestionStatusStore(InMemoryBlobClient())

    store.record(
        source="sharepoint",
        trigger="webhook",
        outcome="success",
        processed=3,
        skipped=1,
        failed=0,
        message="Processed: 3, Skipped (unchanged): 1, Failed: 0",
    )

    latest = store.get_latest()
    assert latest is not None
    assert latest["source"] == "sharepoint"
    assert latest["trigger"] == "webhook"
    assert latest["outcome"] == "success"
    assert latest["processed"] == 3
    assert latest["skipped"] == 1
    assert latest["failed"] == 0
    assert "timestamp" in latest


@pytest.mark.unit
def test_record_overwrites_previous_status() -> None:
    store = IngestionStatusStore(InMemoryBlobClient())

    store.record(source="sharepoint", trigger="webhook", outcome="success", processed=1)
    store.record(source="blob", trigger="manual", outcome="error", failed=2, message="boom")

    latest = store.get_latest()
    assert latest is not None
    assert latest["source"] == "blob"
    assert latest["trigger"] == "manual"
    assert latest["outcome"] == "error"
    assert latest["failed"] == 2
    assert latest["message"] == "boom"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({"processed": 1, "skipped": 0, "failed": 0}, "success"),
        ({"status": "error", "message": "boom"}, "error"),
    ],
)
def test_outcome_from_result(result: dict[str, object], expected: str) -> None:
    assert IngestionStatusStore.outcome_from_result(result) == expected
