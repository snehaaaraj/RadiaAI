"""Models for review history and human disposition loop."""
# ruff: noqa: TC001

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.review_models import (
    CategoryResult,
    DeltaReviewResponse,
    DeterminismContext,
    RequirementReviewResponse,
    RequirementSetReviewResponse,
    ReviewFinding,
    ReviewStatus,
)


class ReviewWorkflow(StrEnum):
    """Supported review workflows tracked in history."""

    REQUIREMENT = "requirement"
    REQUIREMENT_SET = "requirement-set"
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
    category_results: list[CategoryResult] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    determinism: DeterminismContext
    dispositions: list[FindingDisposition] = Field(default_factory=list)


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
        category_results=response.category_results,
        findings=response.findings,
        determinism=response.determinism,
    )


def create_requirement_set_history_entry(
    review_id: str,
    created_at: str,
    subject_id: str | None,
    response: RequirementSetReviewResponse,
) -> ReviewHistoryEntry:
    """Create a normalized history entry from requirement-set response."""
    return ReviewHistoryEntry(
        review_id=review_id,
        workflow=ReviewWorkflow.REQUIREMENT_SET,
        subject_id=subject_id,
        created_at=created_at,
        overall=response.overall,
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
    for requirement_result in response.reviewed_requirements:
        findings.extend(requirement_result.findings)
        category_results.extend(requirement_result.category_results)

    findings.extend(response.requirement_set_findings)
    return ReviewHistoryEntry(
        review_id=review_id,
        workflow=ReviewWorkflow.DELTA,
        subject_id=subject_id,
        created_at=created_at,
        overall=response.overall,
        category_results=category_results,
        findings=findings,
        determinism=response.determinism,
    )
