"""Deterministic requirements review domain models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ReviewStatus(StrEnum):
    """Allowed status values for requirement review outcomes."""

    ACCEPTABLE = "Acceptable"
    REVISION_RECOMMENDED = "Revision Recommended"
    UNACCEPTABLE = "Unacceptable"


class PassFail(StrEnum):
    """Binary pass/fail result for an individual finding."""

    PASS = "Pass"  # noqa: S105 - domain taxonomy value, not a credential
    FAIL = "Fail"


class FindingSeverity(StrEnum):
    """Severity levels used by reviewer findings."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class DeterminismConfigSnapshot(BaseModel):
    """
    Immutable configuration values that influence deterministic output.

    This snapshot is included in review version metadata so clients can verify
    reproducibility conditions for a specific reviewer bundle.
    """

    temperature: float = Field(
        description="Model sampling temperature. Must stay at 0.0 for deterministic reviews."
    )
    max_tokens: int = Field(description="Maximum completion token budget.")
    retrieval_top_k: int = Field(description="Configured retrieval depth used by review engines.")


class DeterminismContext(BaseModel):
    """Versioned context required to reproduce deterministic results."""

    reviewer_bundle_version: str = Field(
        description="Version of the reviewer implementation bundle."
    )
    prompt_versions: dict[str, str] = Field(
        default_factory=dict,
        description="Version map for prompt templates by reviewer category.",
    )
    standards_versions: dict[str, str] = Field(
        default_factory=dict,
        description="Version map for standards and references used by the review.",
    )
    config_hash: str = Field(description="Stable hash of deterministic runtime configuration.")
    config_snapshot: DeterminismConfigSnapshot


class ReviewFinding(BaseModel):
    """Single explainable review finding."""

    category: str = Field(description="Finding category (language, structure, traceability, etc.).")
    reviewer: str = Field(description="Reviewer module that produced this finding.")
    severity: FindingSeverity
    pass_fail: PassFail
    status: ReviewStatus
    rule: str = Field(description="Rule statement being enforced.")
    explanation: str = Field(description="Why the finding was produced.")
    evidence: str = Field(description="Specific text/evidence from the reviewed requirement(s).")
    recommendation: str = Field(description="Actionable remediation guidance.")
    reference: str = Field(description="Standard or guide reference identifier.")


class ReviewerResult(BaseModel):
    """Result produced by an individual reviewer module."""

    reviewer: str = Field(description="Reviewer module name.")
    reviewer_version: str = Field(description="Reviewer module version.")
    prompt_version: str = Field(description="Prompt template version used by reviewer.")
    standards_version: str = Field(description="Standards reference version used by reviewer.")
    overall: ReviewStatus
    findings: list[ReviewFinding] = Field(default_factory=list)


class RequirementReviewInput(BaseModel):
    """Input payload for single-requirement deterministic review."""

    requirement_id: str | None = None
    text: str = Field(min_length=1, description="Requirement text to review.")
    requirement_level: str | None = Field(
        default=None,
        description="Requirement hierarchy level (aircraft/system/subsystem/component).",
    )
    metadata: dict[str, str] = Field(default_factory=dict)


class RequirementSetReviewInput(BaseModel):
    """Input payload for requirement-set review."""

    specification_id: str | None = None
    requirements: list[RequirementReviewInput] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class ReviewVersionEntry(BaseModel):
    """Version metadata for a single reviewer implementation."""

    reviewer: str
    reviewer_version: str
    prompt_version: str
    standards_version: str
    supports_individual_review: bool = False
    supports_requirement_set_review: bool = False


class ReviewVersionResponse(BaseModel):
    """Structured version response returned by GET /review/version."""

    product: str
    workflow_default: str = Field(description="Default production workflow.")
    determinism: DeterminismContext
    reviewers: list[ReviewVersionEntry] = Field(default_factory=list)


class CategoryResult(BaseModel):
    """Normalized category-level status output for requirement review."""

    category: str
    status: ReviewStatus


class RequirementReviewResponse(BaseModel):
    """Aggregated deterministic response for single-requirement review."""

    review_id: str | None = None
    overall: ReviewStatus
    category_results: list[CategoryResult] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    determinism: DeterminismContext


class RequirementSetReviewResponse(BaseModel):
    """Aggregated deterministic response for requirement-set review."""

    review_id: str | None = None
    overall: ReviewStatus
    category_results: list[CategoryResult] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    requirement_count: int = 0
    determinism: DeterminismContext


class TraceLinkChangeType(StrEnum):
    """Supported trace-link delta operations."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class TraceLinkChange(BaseModel):
    """Represents a changed traceability link during delta review."""

    requirement_id: str
    change_type: TraceLinkChangeType
    previous_parent_id: str | None = None
    current_parent_id: str | None = None


class DeltaChangeSummary(BaseModel):
    """Changed item summary for delta review mode."""

    new_requirement_ids: list[str] = Field(default_factory=list)
    modified_requirement_ids: list[str] = Field(default_factory=list)
    deleted_requirement_ids: list[str] = Field(default_factory=list)
    changed_trace_link_requirement_ids: list[str] = Field(default_factory=list)


class DeltaRequirementReviewResult(BaseModel):
    """Per-requirement review result included in delta review response."""

    requirement_id: str
    overall: ReviewStatus
    category_results: list[CategoryResult] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)


class DeltaReviewInput(BaseModel):
    """Input payload for deterministic delta review."""

    specification_id: str | None = None
    baseline_requirements: list[RequirementReviewInput] = Field(default_factory=list)
    updated_requirements: list[RequirementReviewInput] = Field(default_factory=list)
    changed_trace_links: list[TraceLinkChange] = Field(default_factory=list)


class DeltaReviewResponse(BaseModel):
    """Deterministic response for delta review mode."""

    review_id: str | None = None
    overall: ReviewStatus
    change_summary: DeltaChangeSummary
    reviewed_requirements: list[DeltaRequirementReviewResult] = Field(default_factory=list)
    requirement_set_findings: list[ReviewFinding] = Field(default_factory=list)
    determinism: DeterminismContext
