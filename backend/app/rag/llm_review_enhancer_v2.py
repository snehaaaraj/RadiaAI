"""
Consolidated LLM review enhancer — single GPT-5 call for all categories.

Makes one standards-grounded RAG and LLM call covering language, structure,
verifiability, and certification.
"""

from __future__ import annotations

import json
import re
from typing import Any

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

        _log_retrieved_context(context)

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
        chunk_refs = context.chunk_references()
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

            evidence = f.get("evidence", "")
            explanation = f.get("explanation", "")
            matched_chunk = _match_best_chunk(reference, evidence, explanation, chunk_refs)

            findings.append(
                ReviewFinding(
                    category=f.get("category", "General"),
                    reviewer=reviewer,
                    severity=severity,
                    pass_fail=PassFail.FAIL if status != ReviewStatus.ACCEPTABLE else PassFail.PASS,
                    status=status,
                    rule=f.get("rule", ""),
                    explanation=explanation,
                    evidence=evidence,
                    recommendation=f.get("recommendation", ""),
                    reference=reference,
                    reference_title=reference,
                    # A verification pass scores a revision; it must never hand back
                    # replacement text, even if the model volunteers some.
                    suggested_rewrite=f.get("suggested_rewrite") if allow_rewrite else None,
                    source_page=matched_chunk.get("page_number") if matched_chunk else None,
                    source_section=matched_chunk.get("section") or None if matched_chunk else None,
                    source_excerpt=_trim_excerpt(matched_chunk.get("content", ""))
                    if matched_chunk
                    else None,
                    source_chunk_id=matched_chunk.get("chunk_id") or None
                    if matched_chunk
                    else None,
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


_EXCERPT_MAX_CHARS = 400
_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "shall",
    "should",
    "must",
    "be",
    "is",
    "are",
    "with",
    "this",
    "that",
    "it",
}


def _match_best_chunk(
    reference: str,
    evidence: str,
    explanation: str,
    chunk_refs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Find the retrieved chunk whose content best matches a finding, deterministically.

    The LLM is not trusted to self-report which page or chunk it used — its
    citations can be plausible-sounding but wrong. Instead this scores every
    chunk retrieved for this review by token overlap with the finding's
    evidence/explanation text (and reference/filename as a tie-breaker), and
    returns the best match. This is intentionally a simple, explainable
    heuristic rather than a second LLM call, so it is fast, free, and its
    result can be reasoned about by a human when questioned.
    """
    if not chunk_refs:
        return None

    query_text = f"{evidence} {explanation}".strip()
    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return None

    candidates = chunk_refs
    if reference:
        ref_norm = reference.lower()
        filtered = [c for c in chunk_refs if ref_norm in c.get("filename", "").lower()]
        if filtered:
            candidates = filtered

    best_chunk: dict[str, Any] | None = None
    best_score = 0
    for chunk in candidates:
        chunk_tokens = _tokenize(chunk.get("content", ""))
        score = len(query_tokens & chunk_tokens)
        if score > best_score:
            best_score = score
            best_chunk = chunk

    return best_chunk if best_score > 0 else None


def _tokenize(text: str) -> set[str]:
    """Lowercase, split on non-alphanumerics, and drop stopwords/short tokens."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _trim_excerpt(content: str) -> str | None:
    """Trim a chunk's content to a UI-friendly excerpt length."""
    if not content:
        return None
    stripped = content.strip()
    if len(stripped) <= _EXCERPT_MAX_CHARS:
        return stripped
    return stripped[:_EXCERPT_MAX_CHARS].rsplit(" ", 1)[0] + "…"


def _log_retrieved_context(context: RetrievedContext) -> None:
    """
    Log the full retrieval set for this review call, for audit/dispute resolution.

    Even when page/section isn't surfaced to the end user for a given finding,
    this makes it possible to reconstruct exactly what was retrieved and shown
    to the LLM for any review call, by grepping logs for the query text.
    """
    logger.info(
        "consolidated_review_context_retrieved",
        query=context.query,
        mode=context.mode,
        chunk_count=len(context.chunks),
        chunks=[
            {
                "chunk_id": c.get("chunk_id", ""),
                "filename": c.get("filename", ""),
                "section": c.get("section", ""),
                "page_number": c.get("page_number"),
                "score": c.get("score"),
            }
            for c in context.chunks
        ],
    )
