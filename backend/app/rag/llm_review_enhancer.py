"""
LLM-powered review enhancer.

Takes deterministic rule-based findings and enhances them with GPT-5 + RAG:
- Generates proper suggested rewrites grounded in standards documents
- Resolves references to actual indexed document filenames
- Provides deeper analysis when deterministic rules flag an issue
- Generates entirely new findings for categories that rules can't cover
  (traceability, certification)
"""

from __future__ import annotations

import json
from typing import Any

from app.core.logging import get_logger
from app.prompts.review_prompts import (
    CERTIFICATION_REVIEW_SYSTEM,
    LANGUAGE_REVIEW_SYSTEM,
    STRUCTURE_REVIEW_SYSTEM,
    TRACEABILITY_REVIEW_SYSTEM,
    VERIFIABILITY_REVIEW_SYSTEM,
)
from app.rag.service import RAGService, RetrievedContext
from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    FindingSeverity,
    PassFail,
    RequirementReviewInput,
    ReviewerResult,
    ReviewFinding,
    ReviewStatus,
)

logger = get_logger(__name__)

# Map reviewer names to their system prompts
_REVIEWER_PROMPTS = {
    "language": LANGUAGE_REVIEW_SYSTEM,
    "structure": STRUCTURE_REVIEW_SYSTEM,
    "verifiability": VERIFIABILITY_REVIEW_SYSTEM,
    "traceability": TRACEABILITY_REVIEW_SYSTEM,
    "certification": CERTIFICATION_REVIEW_SYSTEM,
}

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


class LLMReviewEnhancer:
    """
    Enhances deterministic review findings with LLM-generated analysis.

    For reviewers that have deterministic rules (language, structure, verifiability):
      - Retrieves relevant standards context via RAG
      - Calls GPT-5 to generate proper rewrites and deeper analysis
      - Replaces hardcoded reference strings with actual document names

    For reviewers without rules (traceability, certification):
      - Generates the entire review via LLM+RAG
    """

    def __init__(self, rag_service: RAGService) -> None:
        self._rag = rag_service

    def enhance_findings(
        self,
        reviewer_name: str,
        payload: RequirementReviewInput,
        deterministic_findings: list[ReviewFinding],
    ) -> list[ReviewFinding]:
        """
        Enhance existing deterministic findings with LLM-generated rewrites
        and references grounded in indexed standards.
        """
        system_prompt = _REVIEWER_PROMPTS.get(reviewer_name)
        if not system_prompt:
            return deterministic_findings

        try:
            # Retrieve relevant standards context
            context = self._retrieve_context(reviewer_name, payload.text)

            if not context.has_context:
                logger.warning("no_rag_context_available", reviewer=reviewer_name)
                return deterministic_findings

            # Build the user message including the requirement and existing findings
            user_message = self._build_enhancement_prompt(payload, deterministic_findings)

            raw_response = self._rag.generate_with_context(
                system_prompt=system_prompt,
                user_message=user_message,
                context=context,
            )
            llm_findings = self._parse_llm_response(raw_response, reviewer_name, context)
        except Exception:
            logger.exception("llm_enhancement_failed", reviewer=reviewer_name)
            return deterministic_findings

        # Merge: use LLM findings to enhance deterministic ones
        return self._merge_findings(deterministic_findings, llm_findings, context)

    def generate_full_review(
        self,
        reviewer_name: str,
        payload: RequirementReviewInput,
    ) -> list[ReviewFinding]:
        """
        Generate a complete review via LLM+RAG for reviewers without deterministic rules.
        Used by traceability and certification reviewers.
        """
        system_prompt = _REVIEWER_PROMPTS.get(reviewer_name)
        if not system_prompt:
            return []

        try:
            context = self._retrieve_context(reviewer_name, payload.text)

            user_message = (
                f"## Requirement to Review\n\n"
                f"**Requirement ID:** {payload.requirement_id or 'N/A'}\n"
                f"**Requirement Level:** {payload.requirement_level or 'not specified'}\n"
                f"**Text:** {payload.text}\n"
            )
            if payload.metadata:
                user_message += f"**Metadata:** {json.dumps(payload.metadata)}\n"

            raw_response = self._rag.generate_with_context(
                system_prompt=system_prompt,
                user_message=user_message,
                context=context,
            )
            return self._parse_llm_response(raw_response, reviewer_name, context)
        except Exception:
            logger.exception("llm_full_review_failed", reviewer=reviewer_name)
            return []

    def _retrieve_context(self, reviewer_name: str, requirement_text: str) -> RetrievedContext:
        """Build a search query and retrieve relevant standards context."""
        # Construct a targeted query combining the reviewer domain with the requirement
        domain_keywords = {
            "language": "requirement language modal verbs ambiguous wording style guide",
            "structure": "requirement structure EARS syntax atomic single requirement",
            "verifiability": "verifiable testable measurable acceptance criteria verification",
            "traceability": "traceability parent child allocation derived requirements",
            "certification": "certification DO-178 DO-254 ARP4754 design assurance level safety",
        }
        domain = domain_keywords.get(reviewer_name, "requirements engineering")
        query = f"{domain} {requirement_text[:200]}"

        # Use top_k=10 to ensure coverage across all indexed standard documents
        return self._rag.retrieve(query, mode="hybrid", top_k=10, diversify=True)

    def _build_enhancement_prompt(
        self,
        payload: RequirementReviewInput,
        findings: list[ReviewFinding],
    ) -> str:
        """Build a user message for enhancing existing deterministic findings."""
        parts = [
            "## Requirement to Review\n",
            f"**Requirement ID:** {payload.requirement_id or 'N/A'}",
            f"**Requirement Level:** {payload.requirement_level or 'not specified'}",
            f"**Text:** {payload.text}\n",
            "## Deterministic Analysis Results\n",
            "The following issues were detected by rule-based checks. "
            "Enhance each finding with a proper suggested rewrite that follows "
            "the standards in the context, and identify the EXACT source document.\n",
        ]
        for i, f in enumerate(findings, 1):
            parts.append(
                f"{i}. [{f.category}] {f.explanation} | Evidence: {f.evidence}"
            )
        if not findings:
            parts.append(
                "No deterministic issues found. Perform a deeper analysis based on "
                "the standards to identify any issues the rules may have missed."
            )
        return "\n".join(parts)

    def _parse_llm_response(
        self,
        raw: str,
        reviewer_name: str,
        context: RetrievedContext,
    ) -> list[ReviewFinding]:
        """Parse the JSON response from the LLM into ReviewFinding objects."""
        try:
            # Strip markdown code fences if present
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()

            data = json.loads(clean)
            raw_findings = data.get("findings", [])
        except (json.JSONDecodeError, KeyError):
            logger.warning("llm_response_parse_failed", reviewer=reviewer_name, raw=raw[:200])
            return []

        source_filenames = {r["filename"] for r in context.source_references()}
        findings = []
        for f in raw_findings:
            severity = _SEVERITY_MAP.get(f.get("severity", "").lower(), FindingSeverity.MEDIUM)
            status = _STATUS_FROM_SEVERITY.get(severity, ReviewStatus.REVISION_RECOMMENDED)

            # Validate reference against actual indexed documents
            reference = f.get("reference", "")
            reference_title = reference
            if reference and reference not in source_filenames:
                # Try fuzzy match
                matched = _fuzzy_match_reference(reference, source_filenames)
                if matched:
                    reference = matched
                    reference_title = matched

            findings.append(
                ReviewFinding(
                    category=f.get("category", "General"),
                    reviewer=reviewer_name,
                    severity=severity,
                    pass_fail=PassFail.FAIL if status != ReviewStatus.ACCEPTABLE else PassFail.PASS,
                    status=status,
                    rule=f.get("rule", ""),
                    explanation=f.get("explanation", ""),
                    evidence=f.get("evidence", ""),
                    recommendation=f.get("recommendation", ""),
                    reference=reference,
                    reference_title=reference_title,
                    suggested_rewrite=f.get("suggested_rewrite"),
                )
            )

        return findings

    def _merge_findings(
        self,
        deterministic: list[ReviewFinding],
        llm: list[ReviewFinding],
        context: RetrievedContext,
    ) -> list[ReviewFinding]:
        """
        Merge deterministic and LLM findings.

        Strategy:
        - For each deterministic finding, try to find a matching LLM finding
          by category and use its suggested_rewrite and reference.
        - Add any LLM findings for categories not covered by deterministic checks.
        """
        llm_by_category: dict[str, ReviewFinding] = {}
        for f in llm:
            key = f.category.lower().strip()
            if key not in llm_by_category:
                llm_by_category[key] = f

        merged = []
        used_categories: set[str] = set()

        for det_finding in deterministic:
            det_key = det_finding.category.lower().strip()
            used_categories.add(det_key)

            llm_match = llm_by_category.get(det_key)
            if llm_match:
                # Enhance deterministic finding with LLM data
                updates: dict[str, Any] = {}
                if llm_match.suggested_rewrite:
                    updates["suggested_rewrite"] = llm_match.suggested_rewrite
                if llm_match.reference:
                    updates["reference"] = llm_match.reference
                    updates["reference_title"] = llm_match.reference_title
                if llm_match.recommendation:
                    updates["recommendation"] = llm_match.recommendation
                if updates:
                    merged.append(det_finding.model_copy(update=updates))
                else:
                    merged.append(det_finding)
            else:
                merged.append(det_finding)

        # Add LLM-only findings for categories not covered by deterministic rules
        for llm_finding in llm:
            llm_key = llm_finding.category.lower().strip()
            if llm_key not in used_categories:
                merged.append(llm_finding)
                used_categories.add(llm_key)

        return merged


def _fuzzy_match_reference(reference: str, filenames: set[str]) -> str | None:
    """Try to match an LLM-generated reference to an actual indexed filename."""
    ref_lower = reference.lower().replace(" ", "").replace("-", "").replace("_", "")
    for fn in filenames:
        fn_lower = fn.lower().replace(" ", "").replace("-", "").replace("_", "")
        # Check if the reference is a substring or vice versa
        if ref_lower in fn_lower or fn_lower in ref_lower:
            return fn
        # Check for significant overlap in words
        ref_words = set(reference.lower().split())
        fn_words = set(fn.lower().replace("-", " ").replace("_", " ").split())
        if len(ref_words & fn_words) >= 2:
            return fn
    return None
