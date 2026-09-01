"""
Consolidated LLM review enhancer — single GPT-5 call for all categories.

Makes one standards-grounded RAG and LLM call covering language, structure,
verifiability, and certification.
"""

from __future__ import annotations

import json

from app.core.logging import get_logger
from app.prompts.review_prompts import CONSOLIDATED_REVIEW_SYSTEM, DELTA_REVIEW_SYSTEM
from app.rag.service import RAGService, RetrievedContext
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    REVIEW_CATEGORIES,
    ConsolidatedReviewResult,
    FindingSeverity,
    PassFail,
    RequirementReviewInput,
    RequirementRevision,
    ReviewCategory,
    ReviewCompletion,
    ReviewFailureReason,
    ReviewFinding,
    ReviewStatus,
)

logger = get_logger(__name__)

_SEVERITY_MAP = {
    "low": FindingSeverity.LOW,
    "medium": FindingSeverity.MEDIUM,
    "high": FindingSeverity.HIGH,
    "critical": FindingSeverity.CRITICAL,
}

_STATUS_FROM_SEVERITY = {
    FindingSeverity.LOW: ReviewStatus.REVISION_RECOMMENDED,
    FindingSeverity.MEDIUM: ReviewStatus.REVISION_RECOMMENDED,
    FindingSeverity.HIGH: ReviewStatus.UNACCEPTABLE,
    FindingSeverity.CRITICAL: ReviewStatus.UNACCEPTABLE,
}

_VALID_REVIEWERS = {category.value for category in REVIEW_CATEGORIES}


class LLMReviewEnhancer:
    """
    Single consolidated LLM call for all review categories.

    Retrieves diverse standards context via RAG, then makes ONE GPT-5 call
    that produces findings across all scored review categories simultaneously.
    """

    def __init__(self, rag_service: RAGService) -> None:
        self._rag = rag_service

    def consolidated_review(
        self,
        payload: RequirementReviewInput,
    ) -> ConsolidatedReviewResult:
        """
        Run a single LLM call covering all review categories.

        Returns findings spanning language, structure, verifiability, and
        certification — all from one GPT-5 invocation — together with a
        completion record. Each pipeline stage is guarded separately so a failure
        is reported with its specific cause instead of collapsing into an empty
        result that would read as "this requirement is clean".
        """
        user_message = (
            f"Requirement ID: {payload.requirement_id or 'N/A'}\n"
            f"Requirement Level: {payload.requirement_level or 'not specified'}\n"
            f"Text: {payload.text}"
        )
        return self._run_review(
            payload.text,
            system_prompt=CONSOLIDATED_REVIEW_SYSTEM,
            user_message=user_message,
            allow_rewrite=True,
        )

    def score_revision(self, revision: RequirementRevision) -> ConsolidatedReviewResult:
        """
        Score an already-revised requirement without proposing further rewrites.

        Delta review verifies a revision rather than authoring one, so findings
        returned here never carry a ``suggested_rewrite``. The baseline text is
        included when available so the model can confirm the revision resolved
        the earlier problems instead of re-raising them.
        """
        payload = revision.requirement
        previous = revision.baseline_text or "(none — this requirement is newly added)"
        user_message = (
            f"Requirement ID: {payload.requirement_id or 'N/A'}\n"
            f"Requirement Level: {payload.requirement_level or 'not specified'}\n"
            f"Previous version: {previous}\n"
            f"Revised text to score: {payload.text}"
        )
        return self._run_review(
            payload.text,
            system_prompt=DELTA_REVIEW_SYSTEM,
            user_message=user_message,
            allow_rewrite=False,
        )

    def _run_review(
        self,
        requirement_text: str,
        *,
        system_prompt: str,
        user_message: str,
        allow_rewrite: bool,
    ) -> ConsolidatedReviewResult:
        """Retrieve standards context and run one guarded LLM review call."""
        try:
            context = self._retrieve_context(requirement_text)
        except Exception:
            logger.exception("consolidated_review_retrieval_failed")
            return _failure(ReviewFailureReason.RETRIEVAL_FAILED)

        if not context.has_context:
            logger.warning("no_rag_context_for_consolidated_review")
            return _failure(ReviewFailureReason.NO_STANDARDS_CONTEXT)

        try:
            raw_response = self._rag.generate_with_context(
                system_prompt=system_prompt,
                user_message=user_message,
                context=context,
            )
        except Exception:
            logger.exception("consolidated_review_llm_call_failed")
            return _failure(ReviewFailureReason.LLM_CALL_FAILED)

        findings = self._parse_response(raw_response, context, allow_rewrite=allow_rewrite)
        if findings is None:
            return _failure(ReviewFailureReason.INVALID_LLM_RESPONSE)

        return ConsolidatedReviewResult(
            findings=findings,
            completion=ReviewCompletion.complete(),
        )

    def _retrieve_context(self, requirement_text: str) -> RetrievedContext:
        """Retrieve diverse standards context for the consolidated review."""
        query = f"requirement engineering standards {requirement_text[:200]}"
        return self._rag.retrieve(query, mode="hybrid", top_k=10, diversify=True)

    def _parse_response(
        self,
        raw: str,
        context: RetrievedContext,
        *,
        allow_rewrite: bool = True,
    ) -> list[ReviewFinding] | None:
        """
        Parse the JSON response from the consolidated LLM call.

        Returns the parsed findings, or None when the response was not usable —
        which the caller reports as a failed review rather than a clean one.
        """
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()

            data = json.loads(clean)
        except json.JSONDecodeError:
            logger.warning("consolidated_llm_parse_failed", raw=raw[:200])
            return None

        if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
            logger.warning("consolidated_llm_response_shape_invalid", raw=raw[:200])
            return None

        raw_findings = data["findings"]
        source_filenames = {r["filename"] for r in context.source_references()}
        findings = []

        for f in raw_findings:
            if not isinstance(f, dict):
                logger.warning("consolidated_llm_finding_skipped_not_an_object")
                continue

            severity = _SEVERITY_MAP.get(f.get("severity", "").lower(), FindingSeverity.MEDIUM)
            status = _STATUS_FROM_SEVERITY.get(severity, ReviewStatus.REVISION_RECOMMENDED)
            reviewer = f.get("reviewer", "").lower().strip()
            if reviewer not in _VALID_REVIEWERS:
                logger.warning("consolidated_llm_finding_reviewer_coerced", reviewer=reviewer)
                reviewer = ReviewCategory.LANGUAGE.value

            reference = f.get("reference", "")
            if reference and reference not in source_filenames:
                matched = _fuzzy_match_reference(reference, source_filenames)
                if matched:
                    reference = matched

            findings.append(
                ReviewFinding(
                    category=f.get("category", "General"),
                    reviewer=reviewer,
                    severity=severity,
                    pass_fail=PassFail.FAIL if status != ReviewStatus.ACCEPTABLE else PassFail.PASS,
                    status=status,
                    rule=f.get("rule", ""),
                    explanation=f.get("explanation", ""),
                    evidence=f.get("evidence", ""),
                    recommendation=f.get("recommendation", ""),
                    reference=reference,
                    reference_title=reference,
                    # A verification pass scores a revision; it must never hand back
                    # replacement text, even if the model volunteers some.
                    suggested_rewrite=f.get("suggested_rewrite") if allow_rewrite else None,
                )
            )

        return findings


def _failure(reason: ReviewFailureReason) -> ConsolidatedReviewResult:
    """Build an empty result that explicitly records why the review did not run."""
    return ConsolidatedReviewResult(findings=[], completion=ReviewCompletion.failed(reason))


def _fuzzy_match_reference(reference: str, filenames: set[str]) -> str | None:
    """Match an LLM-generated reference to an actual indexed filename."""
    ref_lower = reference.lower().replace(" ", "").replace("-", "").replace("_", "")
    for fn in filenames:
        fn_lower = fn.lower().replace(" ", "").replace("-", "").replace("_", "")
        if ref_lower in fn_lower or fn_lower in ref_lower:
            return fn
        ref_words = set(reference.lower().split())
        fn_words = set(fn.lower().replace("-", " ").replace("_", " ").split())
        if len(ref_words & fn_words) >= 2:
            return fn
    return None
