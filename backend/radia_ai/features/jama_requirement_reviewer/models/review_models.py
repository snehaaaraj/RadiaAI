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


class SourceType(StrEnum):
    """Kind of source that backs a recommendation or a rule."""

    SKILLZ_RULE = "skillz_rule"
    STANDARD = "standard"


SOURCE_AUTHORITY_LEVEL: dict[SourceType, int] = {
    SourceType.SKILLZ_RULE: 1,
    SourceType.STANDARD: 2,
}
"""
The application-defined authority hierarchy (1 = highest).

Skillz requirements-writing rules outrank findings grounded in indexed standards
documents. Sources on the same level never override one another. This mapping -
not the LLM - decides which source wins a conflict; synthesis output that claims
otherwise is rejected by the validator.
"""


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
    requirement with no findings and ``status=FAILED`` was never evaluated - the
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

    finding_id: str | None = Field(
        default=None,
        description=(
            "Stable identifier of the finding within its review (F1, F2, ...), used by the "
            "final recommendation to trace each contribution back to this finding."
        ),
    )
    source_type: SourceType = Field(
        default=SourceType.STANDARD,
        description="Kind of source the finding is grounded in.",
    )
    authority_level: int = Field(
        default=SOURCE_AUTHORITY_LEVEL[SourceType.STANDARD],
        description="Application-defined authority level of the source (1 = highest).",
    )
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
    Category-level score and status for a requirement review.

    A completed review emits one of these for every category in
    ``REVIEW_CATEGORIES``, so a category that produced no findings is reported
    as ``ACCEPTABLE`` rather than being omitted and read as "never checked".

    ``score`` is earned from the findings in the category rather than looked up
    from its status, so a clean category scores a full 10 and two failing
    categories can be told apart by how badly they fail. ``status`` is the band
    that score falls in.
    """

    category: str
    status: ReviewStatus
    score: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description="Finding-derived quality score for this category, 0-10.",
    )


class ContributionStatus(StrEnum):
    """How a single finding was treated when the final recommendation was synthesized."""

    APPLIED = "applied"
    MERGED_DUPLICATE = "merged_duplicate"
    OVERRIDDEN = "overridden"
    CONFLICT_UNRESOLVED = "conflict_unresolved"
    REJECTED_UNSUPPORTED = "rejected_unsupported"
    OUT_OF_SCOPE = "out_of_scope"
    NOT_ADDRESSED = "not_addressed"


class ConflictResolution(StrEnum):
    """Outcome of a detected conflict between findings."""

    RESOLVED_BY_SKILLZ = "resolved_by_skillz"
    UNRESOLVED = "unresolved"


class SkillzStatus(StrEnum):
    """Whether Skillz rules governed the final recommendation."""

    APPLIED = "applied"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


class RecommendationStatus(StrEnum):
    """Readiness of the final recommendation to replace the original Description."""

    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    NO_CHANGE = "no_change"
    FAILED = "failed"


class SkillzRuleReference(BaseModel):
    """A Skillz rule cited by the final recommendation, with its full text for audit."""

    rule_id: str = Field(description="Skillz rule identifier, e.g. C18 or Q3.")
    title: str
    document: str = Field(description="Skillz package document the rule comes from.")
    text: str = Field(description="Full rule text as published in the Skillz package.")
    source_url: str | None = Field(default=None, description="SharePoint URL of the package.")
    source_type: SourceType = SourceType.SKILLZ_RULE
    authority_level: int = SOURCE_AUTHORITY_LEVEL[SourceType.SKILLZ_RULE]


class FindingContribution(BaseModel):
    """Traceable account of how one finding affected the final recommendation."""

    finding_id: str
    status: ContributionStatus
    contribution: str = Field(
        default="", description="Short description of the effect on the final text."
    )
    reason: str = Field(default="", description="Why the finding was treated this way.")
    overridden_by_rule_ids: list[str] = Field(
        default_factory=list, description="Skillz rules that override this finding."
    )
    duplicate_of: str | None = Field(
        default=None, description="Finding whose applied change this finding duplicates."
    )
    conflict_id: str | None = Field(
        default=None, description="Conflict this finding participates in, when any."
    )


class SkillzChange(BaseModel):
    """A change required by a Skillz rule that no finding proposed."""

    rule_id: str
    change: str
    reason: str = ""


class RecommendationConflict(BaseModel):
    """A conflict detected between findings and how (or whether) it was resolved."""

    conflict_id: str
    finding_ids: list[str] = Field(default_factory=list)
    description: str = ""
    resolution: ConflictResolution = ConflictResolution.UNRESOLVED
    governing_rule_ids: list[str] = Field(default_factory=list)


class RecommendationOpenItem(BaseModel):
    """Information the synthesis needed but could not safely supply."""

    rule_id: str | None = None
    description: str


class SkillzCheckIssue(BaseModel):
    """A deterministic Skillz rule violation detected in requirement text."""

    rule_id: str
    term: str
    message: str


class FinalRecommendation(BaseModel):
    """
    The single synthesized replacement for the requirement Description.

    The individual findings remain the evidence: every finding is accounted for
    in ``contributions`` with its treatment, and every Skillz rule cited by the
    synthesis is carried in ``skillz_rules``.
    """

    status: RecommendationStatus
    original_description: str
    recommended_description: str | None = None
    summary: str = ""
    skillz_status: SkillzStatus
    skillz_status_message: str = ""
    skillz_package: str | None = None
    skillz_revision: str | None = None
    skillz_content_hash: str | None = None
    skillz_source_url: str | None = None
    contributions: list[FindingContribution] = Field(default_factory=list)
    skillz_changes: list[SkillzChange] = Field(default_factory=list)
    conflicts: list[RecommendationConflict] = Field(default_factory=list)
    open_items: list[RecommendationOpenItem] = Field(default_factory=list)
    skillz_rules: list[SkillzRuleReference] = Field(default_factory=list)
    skillz_check_issues: list[SkillzCheckIssue] = Field(
        default_factory=list,
        description="Skillz violations still present in the recommended text.",
    )
    failure_message: str = ""
    prompt_version: str = ""


class RequirementReviewResponse(BaseModel):
    """Aggregated response for single-requirement review."""

    review_id: str | None = None
    overall: ReviewStatus
    completion: ReviewCompletion = Field(default_factory=ReviewCompletion.complete)
    category_results: list[CategoryResult] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    determinism: DeterminismContext
    requirement_text: str | None = Field(
        default=None, description="The normalized requirement text that was reviewed."
    )
    final_recommendation: FinalRecommendation | None = Field(
        default=None,
        description=(
            "One synthesized replacement Description with full provenance. Null when the "
            "review itself did not complete."
        ),
    )


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
