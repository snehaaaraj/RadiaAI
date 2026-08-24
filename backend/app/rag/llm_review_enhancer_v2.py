"""
Consolidated LLM review enhancer — single GPT-5 call for all categories.

Makes ONE LLM call covering language, structure, verifiability, traceability,
and certification. Runs in parallel with deterministic rule checks via the
orchestrator. Merges LLM findings with deterministic ones.
"""

from __future__ import annotations

import json

from app.core.logging import get_logger
from app.prompts.review_prompts import CONSOLIDATED_REVIEW_SYSTEM
from app.rag.service import RAGService, RetrievedContext
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    FindingSeverity,
    PassFail,
    RequirementReviewInput,
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

_VALID_REVIEWERS = {"language", "structure", "verifiability", "traceability", "certification"}


class LLMReviewEnhancer:
    """
    Single consolidated LLM call for all review categories.

    Retrieves diverse standards context via RAG, then makes ONE GPT-5 call
    that produces findings across all 5 reviewer domains simultaneously.
    """

    def __init__(self, rag_service: RAGService) -> None:
        self._rag = rag_service

    def consolidated_review(
        self,
        payload: RequirementReviewInput,
    ) -> list[ReviewFinding]:
        """
        Run a single LLM call covering all review categories.

        Returns a list of findings spanning language, structure, verifiability,
        traceability, and certification — all from one GPT-5 invocation.
        """
        try:
            context = self._retrieve_context(payload.text)
            if not context.has_context:
                logger.warning("no_rag_context_for_consolidated_review")
                return []

            user_message = (
                f"Requirement ID: {payload.requirement_id or 'N/A'}\n"
                f"Requirement Level: {payload.requirement_level or 'not specified'}\n"
                f"Text: {payload.text}"
            )

            raw_response = self._rag.generate_with_context(
                system_prompt=CONSOLIDATED_REVIEW_SYSTEM,
                user_message=user_message,
                context=context,
            )
            return self._parse_response(raw_response, context)

        except Exception:
            logger.exception("consolidated_llm_review_failed")
            return []

    def _retrieve_context(self, requirement_text: str) -> RetrievedContext:
        """Retrieve diverse standards context for the consolidated review."""
        query = f"requirement engineering standards {requirement_text[:200]}"
        return self._rag.retrieve(query, mode="hybrid", top_k=10, diversify=True)

    def _parse_response(
        self,
        raw: str,
        context: RetrievedContext,
    ) -> list[ReviewFinding]:
        """Parse the JSON response from the consolidated LLM call."""
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()

            data = json.loads(clean)
            raw_findings = data.get("findings", [])
        except (json.JSONDecodeError, KeyError):
            logger.warning("consolidated_llm_parse_failed", raw=raw[:200])
            return []

        source_filenames = {r["filename"] for r in context.source_references()}
        findings = []

        for f in raw_findings:
            severity = _SEVERITY_MAP.get(f.get("severity", "").lower(), FindingSeverity.MEDIUM)
            status = _STATUS_FROM_SEVERITY.get(severity, ReviewStatus.REVISION_RECOMMENDED)
            reviewer = f.get("reviewer", "").lower().strip()
            if reviewer not in _VALID_REVIEWERS:
                reviewer = "language"

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
                    suggested_rewrite=f.get("suggested_rewrite"),
                )
            )

        return findings


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
