"""
Regression tests for Set Review concurrency.

The review pipeline uses synchronous Azure SDK clients. If an ``async def``
endpoint calls them directly, the event loop blocks and concurrent requests
serialise — a set review of N requirements takes N x single-review time and
trips the client's 120s timeout. These tests assert the endpoint offloads that
blocking work so requests genuinely overlap and each result returns as soon as
that requirement is finished.
"""

from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient

from radia_ai.features.jama_requirement_reviewer.dependencies.container import (
    get_requirement_review_service,
    get_review_history_service,
)
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    DeterminismConfigSnapshot,
    DeterminismContext,
    RequirementReviewResponse,
    ReviewCompletion,
    ReviewStatus,
)

CONCURRENT_REQUESTS = 10
SIMULATED_LATENCY_S = 0.3


class _SlowReviewService:
    """Stands in for the real service, blocking like the sync Azure SDK does."""

    def __init__(self) -> None:
        self.max_observed_concurrency = 0
        self._active = 0
        self._lock = threading.Lock()

    def review_requirement(self, payload) -> RequirementReviewResponse:
        with self._lock:
            self._active += 1
            self.max_observed_concurrency = max(self.max_observed_concurrency, self._active)

        # Blocking sleep, exactly like a synchronous HTTP call to Azure OpenAI.
        time.sleep(SIMULATED_LATENCY_S)

        with self._lock:
            self._active -= 1

        return RequirementReviewResponse(
            overall=ReviewStatus.ACCEPTABLE,
            completion=ReviewCompletion.complete(),
            category_results=[],
            findings=[],
            determinism=DeterminismContext(
                reviewer_bundle_version="test",
                config_hash="test-hash",
                config_snapshot=DeterminismConfigSnapshot(
                    temperature=0.0,
                    max_tokens=4096,
                    retrieval_top_k=5,
                ),
            ),
        )


class _StubHistoryService:
    """Avoids real Blob Storage; history persistence is not under test here."""

    def record_requirement_review(self, subject_id, response):
        return f"review-{subject_id}"


@pytest.fixture
def slow_review_app(test_app):
    """Install a review service that reports how many calls overlap."""
    slow_service = _SlowReviewService()
    test_app.dependency_overrides[get_requirement_review_service] = lambda: slow_service
    test_app.dependency_overrides[get_review_history_service] = _StubHistoryService
    yield test_app, slow_service
    test_app.dependency_overrides.pop(get_requirement_review_service, None)
    test_app.dependency_overrides.pop(get_review_history_service, None)


def _post_review(client: TestClient, index: int):
    return client.post(
        "/api/v1/review/requirement",
        json={
            "requirement_id": f"WR-ACR-{index:03d}",
            "text": "The system shall provide a deterministic response within 50 milliseconds.",
            "requirement_level": "Aircraft",
        },
    )


@pytest.mark.unit
def test_concurrent_reviews_overlap(slow_review_app) -> None:
    """
    Ten simultaneous reviews must run in parallel, not one after another.

    With blocking calls on the event loop this observes a concurrency of 1 and
    takes ~10 x latency; correctly offloaded it overlaps and finishes far sooner.
    """
    app, slow_service = slow_review_app

    statuses: list[int] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    with TestClient(app) as client:

        def worker(index: int) -> None:
            try:
                response = _post_review(client, index)
                with lock:
                    statuses.append(response.status_code)
            except BaseException as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(CONCURRENT_REQUESTS)]

        started = time.perf_counter()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        elapsed = time.perf_counter() - started

    assert not errors, f"requests raised: {errors}"
    assert statuses == [200] * CONCURRENT_REQUESTS

    # The decisive assertion: the reviews actually overlapped.
    assert slow_service.max_observed_concurrency > 1, (
        "Reviews ran one at a time — the endpoint is blocking the event loop. "
        f"max concurrency = {slow_service.max_observed_concurrency}"
    )

    serial_duration = CONCURRENT_REQUESTS * SIMULATED_LATENCY_S
    assert (
        elapsed < serial_duration * 0.7
    ), f"Took {elapsed:.2f}s; serial execution would be ~{serial_duration:.2f}s"
