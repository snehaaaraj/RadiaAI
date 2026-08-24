"""Reviewer orchestration — parallel deterministic + LLM pipeline."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    CategoryResult,
    DeterminismConfigSnapshot,
    DeterminismContext,
    RequirementReviewInput,
    RequirementReviewResponse,
    ReviewFinding,
    ReviewStatus,
    ReviewVersionEntry,
    ReviewVersionResponse,
)
from radia_ai.features.jama_requirement_reviewer.utils.requirement_normalization import (
    normalize_requirement_review_input,
)
from radia_ai.features.jama_requirement_reviewer.utils.review_utils import overall_from_statuses

if TYPE_CHECKING:
    from app.core.config import AppSettings
    from app.rag.llm_review_enhancer_v2 import LLMReviewEnhancer
    from radia_ai.features.jama_requirement_reviewer.reviewers.base import RequirementReviewer
    from radia_ai.features.jama_requirement_reviewer.services.standards_service import (
        StandardsService,
    )


class ReviewOrchestrator:
    """Coordinates deterministic reviewers + a single parallel LLM call."""

    def __init__(
        self,
        settings: AppSettings,
        reviewers: list[RequirementReviewer],
        standards_service: StandardsService | None = None,
        llm_enhancer: LLMReviewEnhancer | None = None,
        reviewer_bundle_version: str = "2.0.0",
    ) -> None:
        self._settings = settings
        self._reviewers = reviewers
        self._standards_service = standards_service
        self._llm_enhancer = llm_enhancer
        self._reviewer_bundle_version = reviewer_bundle_version

    def review_requirement(self, payload: RequirementReviewInput) -> RequirementReviewResponse:
        """Run deterministic rules and LLM review in parallel, then merge."""
        normalized_payload = normalize_requirement_review_input(payload)

        # Run deterministic checks + 1 LLM call concurrently
        deterministic_findings: list[ReviewFinding] = []
        llm_findings: list[ReviewFinding] = []

        with ThreadPoolExecutor(max_workers=2) as executor:
            det_future = executor.submit(self._run_deterministic, normalized_payload)

            llm_future = None
            if self._llm_enhancer is not None:
                llm_future = executor.submit(
                    self._llm_enhancer.consolidated_review, normalized_payload
                )

            deterministic_findings = det_future.result()
            if llm_future is not None:
                llm_findings = llm_future.result()

        # Merge: LLM enhances deterministic findings + adds new categories
        merged = self._merge_findings(deterministic_findings, llm_findings)
        enriched = self._enrich_findings(merged)

        # Build category results from merged findings
        category_statuses: dict[str, list[ReviewStatus]] = {}
        for f in enriched:
            category_statuses.setdefault(f.reviewer, []).append(f.status)

        # Ensure all 5 reviewer categories appear
        for reviewer in self._reviewers:
            if reviewer.name not in category_statuses:
                category_statuses[reviewer.name] = []

        category_results = [
            CategoryResult(
                category=name,
                status=overall_from_statuses(statuses) if statuses else ReviewStatus.ACCEPTABLE,
            )
            for name, statuses in category_statuses.items()
        ]

        overall = overall_from_statuses([cr.status for cr in category_results])
        return RequirementReviewResponse(
            overall=overall,
            category_results=category_results,
            findings=enriched,
            determinism=self.build_version_response().determinism,
        )

    def _run_deterministic(self, payload: RequirementReviewInput) -> list[ReviewFinding]:
        """Run all deterministic reviewer rules (fast, no LLM)."""
        findings = []
        for reviewer in self._reviewers:
            if reviewer.supports_individual_review:
                result = reviewer.review_requirement(payload)
                findings.extend(result.findings)
        return findings

    def _merge_findings(
        self,
        deterministic: list[ReviewFinding],
        llm: list[ReviewFinding],
    ) -> list[ReviewFinding]:
        """
        Merge deterministic and LLM findings.

        - For each deterministic finding, if the LLM produced a matching category,
          use the LLM's suggested_rewrite and reference (grounded in standards).
        - Add LLM-only findings for categories not covered by deterministic rules
          (e.g., traceability, certification).
        """
        if not llm:
            return deterministic

        llm_by_key: dict[str, ReviewFinding] = {}
        for f in llm:
            key = f"{f.reviewer}:{f.category}".lower().strip()
            if key not in llm_by_key:
                llm_by_key[key] = f

        merged = []
        used_keys: set[str] = set()

        for det in deterministic:
            det_key = f"{det.reviewer}:{det.category}".lower().strip()
            used_keys.add(det_key)

            llm_match = llm_by_key.get(det_key)
            if llm_match:
                updates: dict[str, str | None] = {}
                if llm_match.suggested_rewrite:
                    updates["suggested_rewrite"] = llm_match.suggested_rewrite
                if llm_match.reference:
                    updates["reference"] = llm_match.reference
                    updates["reference_title"] = llm_match.reference_title
                if llm_match.recommendation:
                    updates["recommendation"] = llm_match.recommendation
                merged.append(det.model_copy(update=updates) if updates else det)
            else:
                merged.append(det)

        # Add LLM-only findings (traceability, certification, etc.)
        for f in llm:
            key = f"{f.reviewer}:{f.category}".lower().strip()
            if key not in used_keys:
                merged.append(f)
                used_keys.add(key)

        return merged

    def build_version_response(self) -> ReviewVersionResponse:
        """Return deterministic reviewer/prompt/standards version metadata."""
        prompt_versions = {reviewer.name: reviewer.prompt_version for reviewer in self._reviewers}
        standards_versions = {
            reviewer.name: reviewer.standards_version for reviewer in self._reviewers
        }
        config_snapshot = DeterminismConfigSnapshot(
            temperature=self._settings.azure_openai.temperature,
            max_tokens=self._settings.azure_openai.max_tokens,
            retrieval_top_k=self._settings.retrieval_top_k,
        )

        determinism_context = DeterminismContext(
            reviewer_bundle_version=self._reviewer_bundle_version,
            prompt_versions=prompt_versions,
            standards_versions=standards_versions,
            config_hash=self._build_config_hash(
                config_snapshot, prompt_versions, standards_versions
            ),
            config_snapshot=config_snapshot,
        )

        return ReviewVersionResponse(
            product="Radia AI Requirements Engineering Assistant",
            workflow_default="requirement",
            determinism=determinism_context,
            reviewers=[
                ReviewVersionEntry(
                    reviewer=reviewer.name,
                    reviewer_version=reviewer.reviewer_version,
                    prompt_version=reviewer.prompt_version,
                    standards_version=reviewer.standards_version,
                    supports_individual_review=reviewer.supports_individual_review,
                )
                for reviewer in self._reviewers
            ],
        )

    def _build_config_hash(
        self,
        snapshot: DeterminismConfigSnapshot,
        prompt_versions: dict[str, str],
        standards_versions: dict[str, str],
    ) -> str:
        payload = {
            "reviewer_bundle_version": self._reviewer_bundle_version,
            "azure_openai_api_version": self._settings.azure_openai.api_version,
            "azure_openai_chat_deployment": self._settings.azure_openai.chat_deployment,
            "config_snapshot": snapshot.model_dump(mode="json"),
            "prompt_versions": prompt_versions,
            "standards_versions": standards_versions,
        }
        stable_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()

    # Generic fallback labels that need resolution to actual documents
    _FALLBACK_REFERENCES = {
        "incose",
        "ears",
        "company style guide",
        "internal engineering standards",
        "cert-guidance",
        "certification guidance",
        "company-style-guide",
    }

    def _enrich_findings(self, findings: list[ReviewFinding]) -> list[ReviewFinding]:
        """Resolve references to actual SharePoint document names/URLs.

        - Fallback labels (INCOSE, EARS, etc.): resolve both name and URL.
        - Real document names (set by LLM enhancer): keep name, resolve URL only.
        """
        if self._standards_service is None:
            return findings

        enriched = []
        for finding in findings:
            is_fallback = finding.reference.lower().strip() in self._FALLBACK_REFERENCES

            if is_fallback:
                # Resolve both name and URL
                resolved = self._standards_service.resolve_reference(
                    finding.reference,
                    category=finding.category,
                    reviewer=finding.reviewer,
                )
                if resolved and resolved.sharepoint_url:
                    enriched.append(
                        finding.model_copy(
                            update={
                                "reference": resolved.name,
                                "reference_title": resolved.name,
                                "reference_url": resolved.sharepoint_url,
                            }
                        )
                    )
                else:
                    enriched.append(finding)
            elif not finding.reference_url:
                # LLM already set the reference name — just look up the URL
                resolved = self._standards_service.resolve_reference(
                    finding.reference,
                    category=finding.category,
                    reviewer=finding.reviewer,
                )
                if resolved and resolved.sharepoint_url:
                    enriched.append(
                        finding.model_copy(
                            update={
                                "reference_url": resolved.sharepoint_url,
                            }
                        )
                    )
                else:
                    enriched.append(finding)
            else:
                # Already fully resolved
                enriched.append(finding)

        return enriched
