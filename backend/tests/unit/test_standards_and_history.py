"""Unit tests for standards and review history endpoints."""

import pytest
from fastapi.testclient import TestClient

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    ConsolidatedReviewResult,
    ReviewCompletion,
)


@pytest.mark.unit
def test_get_standards_returns_references(client: TestClient) -> None:
    response = client.get("/api/v1/standards")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    standards = body["data"]["standards"]
    assert len(standards) >= 1
    assert any(item["key"] == "incose" for item in standards)


@pytest.mark.unit
def test_review_history_and_disposition_flow(client: TestClient) -> None:
    review_response = client.post(
        "/api/v1/review/requirement",
        json={"requirement_id": "REQ-HIST-1", "text": "The subsystem should respond fast."},
    )
    assert review_response.status_code == 200

    history_response = client.get("/api/v1/review/history")
    assert history_response.status_code == 200
    history_body = history_response.json()
    assert history_body["success"] is True
    entries = history_body["data"]["entries"]
    assert len(entries) >= 1

    latest_entry = entries[0]
    review_id = latest_entry["review_id"]
    assert latest_entry["workflow"] == "requirement"
    assert len(latest_entry["findings"]) >= 1

    disposition_response = client.post(
        f"/api/v1/review/history/{review_id}/disposition",
        json={
            "finding_index": 0,
            "disposition": "Accepted",
            "reviewer_comment": "Acknowledged and accepted for update.",
            "reviewer_id": "engineer@example.com",
        },
    )
    assert disposition_response.status_code == 200
    disposition_body = disposition_response.json()
    assert disposition_body["success"] is True
    dispositions = disposition_body["data"]["dispositions"]
    assert len(dispositions) == 1
    assert dispositions[0]["disposition"] == "Accepted"


@pytest.mark.unit
def test_review_history_rejects_out_of_range_finding_index(
    client: TestClient, review_engine
) -> None:
    """A disposition pointing past the stored findings is rejected, not recorded."""
    review_engine.install(
        ConsolidatedReviewResult(findings=[], completion=ReviewCompletion.complete())
    )

    review_response = client.post(
        "/api/v1/review/requirement",
        json={"requirement_id": "REQ-HIST-EMPTY", "text": "The subsystem shall respond."},
    )
    assert review_response.status_code == 200
    review_id = review_response.json()["data"]["review_id"]

    disposition_response = client.post(
        f"/api/v1/review/history/{review_id}/disposition",
        json={"finding_index": 0, "disposition": "Accepted"},
    )

    assert disposition_response.status_code == 422
    disposition_body = disposition_response.json()
    assert disposition_body["success"] is False
    assert disposition_body["error"]["message"] == "Finding index is out of range for this review."


@pytest.mark.unit
def test_review_history_cleanup_deletes_old_entries(test_app) -> None:
    """Entries older than 10 days are automatically deleted during list."""
    from datetime import UTC, datetime, timedelta

    from radia_ai.features.jama_requirement_reviewer.models.review_history_models import (
        ReviewHistoryEntry,
        ReviewWorkflow,
    )
    from radia_ai.features.jama_requirement_reviewer.models.review_models import (
        DeterminismConfigSnapshot,
        DeterminismContext,
        ReviewStatus,
    )
    from radia_ai.features.jama_requirement_reviewer.repositories.review_history_repository import (
        ReviewHistoryRepository,
    )

    # Get the repository directly from app state
    repo: ReviewHistoryRepository = test_app.state.review_history_repository
    blob_client = repo._blob

    # Create a minimal determinism context
    determinism = DeterminismContext(
        reviewer_bundle_version="1.0.0",
        config_hash="test-hash",
        config_snapshot=DeterminismConfigSnapshot(
            temperature=0.0,
            max_tokens=4096,
            retrieval_top_k=5,
        ),
    )

    # Create an old entry (11 days ago)
    old_entry = ReviewHistoryEntry(
        review_id="old-review-123",
        workflow=ReviewWorkflow.REQUIREMENT,
        created_at=(datetime.now(UTC) - timedelta(days=11)).isoformat(),
        overall=ReviewStatus.REVISION_RECOMMENDED,
        determinism=determinism,
    )
    blob_client.upload_blob(
        "review-history/old-review-123.json",
        old_entry.model_dump_json().encode(),
    )

    # Create a recent entry (2 days ago)
    recent_entry = ReviewHistoryEntry(
        review_id="recent-review-456",
        workflow=ReviewWorkflow.REQUIREMENT,
        created_at=(datetime.now(UTC) - timedelta(days=2)).isoformat(),
        overall=ReviewStatus.ACCEPTABLE,
        determinism=determinism,
    )
    repo.add_entry(recent_entry)

    # Patch the list_blobs to return proper timestamps
    original_list_blobs = blob_client.list_blobs

    def patched_list_blobs(prefix: str = "") -> list:
        blobs = original_list_blobs(prefix)
        for blob in blobs:
            if "old-review" in blob["name"]:
                blob["last_modified"] = (datetime.now(UTC) - timedelta(days=11)).isoformat()
        return blobs

    blob_client.list_blobs = patched_list_blobs

    # List entries — this should trigger cleanup
    entries = repo.list_entries()

    # Only the recent entry should remain
    assert len(entries) == 1
    assert entries[0].review_id == "recent-review-456"
    assert "review-history/old-review-123.json" not in blob_client._blobs
