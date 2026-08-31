"""Models for review history and human disposition loop."""
# ruff: noqa: TC001

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    CategoryResult,
    DeltaReviewResponse,
    DeterminismContext,
    RequirementReviewResponse,
    ReviewCompletion,
    ReviewFinding,
    ReviewStatus,
)


class ReviewWorkflow(StrEnum):
    """Supported review workflows tracked in history."""

    REQUIREMENT = "requirement"
    DELTA = "delta"


class FindingDispositionStatus(StrEnum):
    """Supported reviewer disposition states."""

    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    DEFERRED = "Deferred"


class FindingDisposition(BaseModel):
    """Disposition record for a specific finding index."""

    finding_index: int = Field(ge=0)
    disposition: FindingDispositionStatus
    reviewer_comment: str = ""
    reviewer_id: str | None = None
    updated_at: str


class ApplyFindingDispositionRequest(BaseModel):
    """Request body for applying reviewer disposition to a finding."""

    finding_index: int = Field(ge=0)
    disposition: FindingDispositionStatus
    reviewer_comment: str = ""
    reviewer_id: str | None = None


class ReviewHistoryEntry(BaseModel):
    """Stored record for a completed review run."""

    review_id: str
    workflow: ReviewWorkflow
    subject_id: str | None = None
    created_at: str
    overall: ReviewStatus
    completion: ReviewCompletion = Field(default_factory=ReviewCompletion.complete)
    category_results: list[CategoryResult] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    determinism: DeterminismContext
    dispositions: list[FindingDisposition] = Field(default_factory=list)
    # For delta reviews: map flattened finding index -> requirement_id
    finding_to_requirement_map: dict[int, str] = Field(default_factory=dict)


class ReviewHistoryListResponse(BaseModel):
    """Paginated-style response for review history listing."""

    total: int
    entries: list[ReviewHistoryEntry] = Field(default_factory=list)


def create_requirement_history_entry(
    review_id: str,
    created_at: str,
    subject_id: str | None,
    response: RequirementReviewResponse,
) -> ReviewHistoryEntry:
    """Create a normalized history entry from single requirement response."""
    return ReviewHistoryEntry(
        review_id=review_id,
        workflow=ReviewWorkflow.REQUIREMENT,
        subject_id=subject_id,
        created_at=created_at,
        overall=response.overall,
        completion=response.completion,
        category_results=response.category_results,
        findings=response.findings,
        determinism=response.determinism,
    )


def create_delta_history_entry(
    review_id: str,
    created_at: str,
    subject_id: str | None,
    response: DeltaReviewResponse,
) -> ReviewHistoryEntry:
    """Create a normalized history entry from delta response."""
    findings = []
    category_results = []
    finding_to_requirement_map: dict[int, str] = {}
    global_index = 0

    for requirement_result in response.reviewed_requirements:
        for _ in requirement_result.findings:
            finding_to_requirement_map[global_index] = requirement_result.requirement_id
            global_index += 1
        findings.extend(requirement_result.findings)
        category_results.extend(requirement_result.category_results)

    return ReviewHistoryEntry(
        review_id=review_id,
        workflow=ReviewWorkflow.DELTA,
        subject_id=subject_id,
        created_at=created_at,
        overall=response.overall,
        completion=response.completion,
        category_results=category_results,
        findings=findings,
        determinism=response.determinism,
        finding_to_requirement_map=finding_to_requirement_map,
    )
