"""Reviewer orchestration — LLM-based review pipeline."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    REVIEW_CATEGORIES,
    CategoryResult,
    ConsolidatedReviewResult,
    DeterminismConfigSnapshot,
    DeterminismContext,
    RequirementReviewInput,
    RequirementReviewResponse,
    RequirementRevision,
    ReviewCompletion,
    ReviewFailureReason,
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
    """Coordinates LLM-based requirement reviews."""

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
        """
        Run the consolidated LLM review, proposing a rewrite for each finding.

        When the review engine cannot evaluate the requirement, the response
        carries ``overall = NOT_EVALUATED`` and a failed completion record. An
        unevaluated requirement is never reported as acceptable.
        """
        normalized_payload = normalize_requirement_review_input(payload)

        if self._llm_enhancer is None:
            llm_result = ConsolidatedReviewResult(
                completion=ReviewCompletion.failed(ReviewFailureReason.REVIEW_ENGINE_UNAVAILABLE),
            )
        else:
            llm_result = self._llm_enhancer.consolidated_review(normalized_payload)

        return self._to_response(llm_result)

    def score_revision(self, revision: RequirementRevision) -> RequirementReviewResponse:
        """
        Score an already-revised requirement without proposing further changes.

        Delta review verifies work that a previous review recommended, so this
        path returns category scores and the reasons behind them, but no
        replacement text.
        """
        normalized = revision.model_copy(
            update={"requirement": normalize_requirement_review_input(revision.requirement)}
        )

        if self._llm_enhancer is None:
            llm_result = ConsolidatedReviewResult(
                completion=ReviewCompletion.failed(ReviewFailureReason.REVIEW_ENGINE_UNAVAILABLE),
            )
        else:
            llm_result = self._llm_enhancer.score_revision(normalized)

        return self._to_response(llm_result)

    def _to_response(self, llm_result: ConsolidatedReviewResult) -> RequirementReviewResponse:
        """Turn a raw LLM result into a scored, standards-enriched response."""
        determinism = self.build_version_response().determinism

        if not llm_result.completion.is_complete:
            return RequirementReviewResponse(
                overall=ReviewStatus.NOT_EVALUATED,
                completion=llm_result.completion,
                category_results=[],
                findings=[],
                determinism=determinism,
            )

        enriched = self._enrich_findings(llm_result.findings)
        category_results = self._build_category_results(enriched)
        return RequirementReviewResponse(
            overall=overall_from_statuses([cr.status for cr in category_results]),
            completion=llm_result.completion,
            category_results=category_results,
            findings=enriched,
            determinism=determinism,
        )

    @staticmethod
    def _build_category_results(findings: list[ReviewFinding]) -> list[CategoryResult]:
        """
        Score every review category, not just the ones that produced findings.

        A category the review checked and found nothing wrong with is
        ``ACCEPTABLE``. Omitting it would make a clean category indistinguishable
        from one that was never evaluated.
        """
        statuses: dict[str, list[ReviewStatus]] = {category: [] for category in REVIEW_CATEGORIES}
        for finding in findings:
            # Findings from an unrecognized category are still scored, so an
            # unexpected reviewer value can never silently drop a problem.
            statuses.setdefault(finding.reviewer, []).append(finding.status)

        return [
            CategoryResult(category=category, status=overall_from_statuses(category_statuses))
            for category, category_statuses in statuses.items()
        ]

    def build_version_response(self) -> ReviewVersionResponse:
        """Return reviewer/prompt/standards version metadata."""
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
