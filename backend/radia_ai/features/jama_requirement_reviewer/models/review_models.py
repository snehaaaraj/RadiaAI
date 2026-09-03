"""Requirements review domain models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ReviewStatus(StrEnum):
    """Allowed status values for requirement review outcomes."""

    ACCEPTABLE = "Acceptable"
    REVISION_RECOMMENDED = "Revision Recommended"
    UNACCEPTABLE = "Unacceptable"
    NOT_EVALUATED = "Not Evaluated"


class ReviewCategory(StrEnum):
    """
    The review categories the product scores.

    This is the single source of truth for the scored categories: the prompt,
    the response parser, the orchestrator and the UI grid all derive from it, so
    a category can never be produced by one layer and dropped by another.
    """

    LANGUAGE = "language"
    STRUCTURE = "structure"
    VERIFIABILITY = "verifiability"
    CERTIFICATION = "certification"


REVIEW_CATEGORIES: tuple[ReviewCategory, ...] = (
    ReviewCategory.LANGUAGE,
    ReviewCategory.STRUCTURE,
    ReviewCategory.VERIFIABILITY,
    ReviewCategory.CERTIFICATION,
)
"""Scored categories in the order they are presented to a reviewer."""


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


class ReviewCompletionStatus(StrEnum):
    """Whether the review engine actually managed to evaluate the requirement(s)."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class ReviewFailureReason(StrEnum):
    """Machine-readable cause for a review that did not complete."""

    REVIEW_ENGINE_UNAVAILABLE = "review_engine_unavailable"
    NO_STANDARDS_CONTEXT = "no_standards_context"
    RETRIEVAL_FAILED = "retrieval_failed"
    LLM_CALL_FAILED = "llm_call_failed"
    INVALID_LLM_RESPONSE = "invalid_llm_response"


_FAILURE_MESSAGES: dict[ReviewFailureReason, str] = {
    ReviewFailureReason.REVIEW_ENGINE_UNAVAILABLE: (
        "The AI review engine is not available, so this requirement was not evaluated. "
        "Check the Azure OpenAI and Azure AI Search configuration and try again."
    ),
    ReviewFailureReason.NO_STANDARDS_CONTEXT: (
        "No indexed standards documents matched this requirement, so there was nothing to "
        "review it against. Ingest the standards library and run the review again."
    ),
    ReviewFailureReason.RETRIEVAL_FAILED: (
        "Standards retrieval from Azure AI Search failed, so this requirement was not "
        "evaluated. Try again in a moment."
    ),
    ReviewFailureReason.LLM_CALL_FAILED: (
        "The AI review call did not complete, so this requirement was not evaluated. "
        "Try again in a moment."
    ),
    ReviewFailureReason.INVALID_LLM_RESPONSE: (
        "The AI review returned a response that could not be interpreted, so no findings "
        "could be extracted. Running the review again usually resolves this."
    ),
}

_PARTIAL_MESSAGE_TEMPLATE = (
    "{failed_count} of {total_count} requirements could not be evaluated. "
    "Results below are incomplete."
)


class ReviewCompletion(BaseModel):
    """
    Outcome of the review *process*, kept separate from the review *verdict*.

    A requirement with no findings and ``status=COMPLETE`` genuinely passed. A
    requirement with no findings and ``status=FAILED`` was never evaluated — the
    two must never be presented to a reviewer as the same result.
    """

    status: ReviewCompletionStatus = ReviewCompletionStatus.COMPLETE
    reason: ReviewFailureReason | None = Field(
        default=None,
        description="Machine-readable failure cause. Null when the review completed.",
    )
    message: str = Field(
        default="",
        description="Human-readable explanation shown to the reviewer when incomplete.",
    )

    @property
    def is_complete(self) -> bool:
        return self.status is ReviewCompletionStatus.COMPLETE

    @classmethod
    def complete(cls) -> ReviewCompletion:
        """Build a successful completion record."""
        return cls(status=ReviewCompletionStatus.COMPLETE)

    @classmethod
    def failed(cls, reason: ReviewFailureReason) -> ReviewCompletion:
        """Build a failure record with the standard message for *reason*."""
        return cls(
            status=ReviewCompletionStatus.FAILED,
            reason=reason,
            message=_FAILURE_MESSAGES[reason],
        )

    @classmethod
    def partial(
        cls, reason: ReviewFailureReason, failed_count: int, total_count: int
    ) -> ReviewCompletion:
        """Build a record for a batch where only some items were evaluated."""
        return cls(
            status=ReviewCompletionStatus.PARTIAL,
            reason=reason,
            message=_PARTIAL_MESSAGE_TEMPLATE.format(
                failed_count=failed_count, total_count=total_count
            ),
        )


class DeterminismConfigSnapshot(BaseModel):
    """
    Immutable configuration values that influence deterministic output.

    This snapshot is included in review version metadata so clients can verify
    reproducibility conditions for a specific reviewer bundle.
    """

    temperature: float = Field(description="Model sampling temperature.")
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

    category: str = Field(
        description="Finding sub-category (e.g. Banned Words, EARS Syntax, Operating Conditions)."
    )
    reviewer: str = Field(description="Scored review category that produced this finding.")
    severity: FindingSeverity
    pass_fail: PassFail
    status: ReviewStatus
    rule: str = Field(description="Rule statement being enforced.")
    explanation: str = Field(description="Why the finding was produced.")
    evidence: str = Field(description="Specific text/evidence from the reviewed requirement(s).")
    recommendation: str = Field(description="Actionable remediation guidance.")
    reference: str = Field(description="Standard or guide reference identifier.")
    reference_title: str | None = Field(
        default=None,
        description="Human-readable source document title for the reference.",
    )
    reference_url: str | None = Field(
        default=None,
        description="SharePoint or document URL for the reference source.",
    )
    suggested_rewrite: str | None = Field(
        default=None,
        description=(
            "AI-assisted rephrased version of the requirement text that applies this "
            "finding's recommendation. Intended for use in the Changeset UI section."
        ),
    )
    source_page: int | None = Field(
        default=None,
        description=(
            "Page number within the source document (reference_url) that this finding "
            "was grounded on. Determined by matching the finding's evidence against the "
            "retrieved standards chunks, not by trusting the LLM's own citation."
        ),
    )
    source_section: str | None = Field(
        default=None,
        description="Section/heading within the source document, when detected.",
    )
    source_excerpt: str | None = Field(
        default=None,
        description=(
            "The literal retrieved passage from the source document that most closely "
            "matches this finding, shown so a reviewer can verify the suggestion without "
            "leaving the app."
        ),
    )
    source_chunk_id: str | None = Field(
        default=None,
        description="Identifier of the indexed chunk this finding was matched to, for audit/debug.",
    )


class ConsolidatedReviewResult(BaseModel):
    """
    Return value of the consolidated LLM review call.

    Carries the completion record alongside the findings so callers can tell an
    empty-because-clean review apart from an empty-because-it-broke one.
    """

    findings: list[ReviewFinding] = Field(default_factory=list)
    completion: ReviewCompletion = Field(default_factory=ReviewCompletion.complete)


class ReviewerResult(BaseModel):
    """Result produced by an individual reviewer module."""

    reviewer: str = Field(description="Reviewer module name.")
    reviewer_version: str = Field(description="Reviewer module version.")
    prompt_version: str = Field(description="Prompt template version used by reviewer.")
    standards_version: str = Field(description="Standards reference version used by reviewer.")
    overall: ReviewStatus
    findings: list[ReviewFinding] = Field(default_factory=list)


class RequirementReviewInput(BaseModel):
    """Input payload for single-requirement review."""

    requirement_id: str | None = None
    text: str = Field(min_length=1, description="Requirement text to review.")
    requirement_level: str | None = Field(
        default=None,
        description="Requirement hierarchy level (aircraft/system/subsystem/component).",
    )
    metadata: dict[str, str] = Field(default_factory=dict)


class ReviewVersionEntry(BaseModel):
    """Version metadata for a single reviewer implementation."""

    reviewer: str
    reviewer_version: str
    prompt_version: str
    standards_version: str
    supports_individual_review: bool = False


class ReviewVersionResponse(BaseModel):
    """Structured version response returned by GET /review/version."""

    product: str
    workflow_default: str = Field(description="Default production workflow.")
    determinism: DeterminismContext
    reviewers: list[ReviewVersionEntry] = Field(default_factory=list)


class CategoryResult(BaseModel):
    """
    Category-level status for a requirement review.

    A completed review emits one of these for every category in
    ``REVIEW_CATEGORIES``, so a category that produced no findings is reported
    as ``ACCEPTABLE`` rather than being omitted and read as "never checked".
    """

    category: str
    status: ReviewStatus


class RequirementReviewResponse(BaseModel):
    """Aggregated response for single-requirement review."""

    review_id: str | None = None
    overall: ReviewStatus
    completion: ReviewCompletion = Field(default_factory=ReviewCompletion.complete)
    category_results: list[CategoryResult] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    determinism: DeterminismContext


class DeltaChangeSummary(BaseModel):
    """Changed item summary for delta review mode."""

    new_requirement_ids: list[str] = Field(default_factory=list)
    modified_requirement_ids: list[str] = Field(default_factory=list)
    deleted_requirement_ids: list[str] = Field(default_factory=list)


class RequirementRevision(BaseModel):
    """
    A changed requirement paired with the baseline version it replaces.

    Delta review scores a revision, so the reviewer needs the previous text to
    confirm the revision actually resolved the earlier findings. ``baseline_text``
    is null for a newly added requirement, which has nothing to compare against.
    """

    key: str = Field(
        description="Identifier pairing this requirement with its baseline, and labelling the result."
    )
    requirement: RequirementReviewInput
    baseline_text: str | None = None


class DeltaRequirementReviewResult(BaseModel):
    """Per-requirement review result included in delta review response."""

    requirement_id: str
    overall: ReviewStatus
    completion: ReviewCompletion = Field(default_factory=ReviewCompletion.complete)
    category_results: list[CategoryResult] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)


class DeltaReviewInput(BaseModel):
    """Input payload for deterministic delta review."""

    specification_id: str | None = None
    baseline_requirements: list[RequirementReviewInput] = Field(default_factory=list)
    updated_requirements: list[RequirementReviewInput] = Field(default_factory=list)


class DeltaReviewResponse(BaseModel):
    """Response for delta review mode."""

    review_id: str | None = None
    overall: ReviewStatus
    completion: ReviewCompletion = Field(default_factory=ReviewCompletion.complete)
    change_summary: DeltaChangeSummary
    reviewed_requirements: list[DeltaRequirementReviewResult] = Field(default_factory=list)
    determinism: DeterminismContext
