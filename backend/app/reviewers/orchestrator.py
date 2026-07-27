"""Reviewer orchestration and version catalog."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

from app.models.review_models import (
    CategoryResult,
    DeterminismConfigSnapshot,
    DeterminismContext,
    RequirementReviewInput,
    RequirementReviewResponse,
    RequirementSetReviewInput,
    RequirementSetReviewResponse,
    ReviewStatus,
    ReviewVersionEntry,
    ReviewVersionResponse,
)

if TYPE_CHECKING:
    from app.core.config import AppSettings
    from app.reviewers.base import RequirementReviewer


class ReviewOrchestrator:
    """Coordinates reviewer modules and exposes deterministic version metadata."""

    def __init__(
        self,
        settings: AppSettings,
        reviewers: list[RequirementReviewer],
        reviewer_bundle_version: str = "1.0.0",
    ) -> None:
        self._settings = settings
        self._reviewers = reviewers
        self._reviewer_bundle_version = reviewer_bundle_version

    def review_requirement(self, payload: RequirementReviewInput) -> RequirementReviewResponse:
        """Run all reviewers that support individual requirement review."""
        reviewer_results = [
            reviewer.review_requirement(payload)
            for reviewer in self._reviewers
            if reviewer.supports_individual_review
        ]
        findings = [finding for result in reviewer_results for finding in result.findings]
        category_results = [
            CategoryResult(category=result.reviewer, status=result.overall)
            for result in reviewer_results
        ]
        overall = _overall_from_statuses([result.overall for result in reviewer_results])
        return RequirementReviewResponse(
            overall=overall,
            category_results=category_results,
            findings=findings,
            determinism=self.build_version_response().determinism,
        )

    def review_requirement_set(
        self, payload: RequirementSetReviewInput
    ) -> RequirementSetReviewResponse:
        """Run all reviewers that support requirement set review."""
        reviewer_results = [
            reviewer.review_requirement_set(payload)
            for reviewer in self._reviewers
            if reviewer.supports_requirement_set_review
        ]
        findings = [finding for result in reviewer_results for finding in result.findings]
        category_results = [
            CategoryResult(category=result.reviewer, status=result.overall)
            for result in reviewer_results
        ]
        overall = _overall_from_statuses([result.overall for result in reviewer_results])
        return RequirementSetReviewResponse(
            overall=overall,
            category_results=category_results,
            findings=findings,
            requirement_count=len(payload.requirements),
            determinism=self.build_version_response().determinism,
        )

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
            workflow_default="requirement-set-review",
            determinism=determinism_context,
            reviewers=[
                ReviewVersionEntry(
                    reviewer=reviewer.name,
                    reviewer_version=reviewer.reviewer_version,
                    prompt_version=reviewer.prompt_version,
                    standards_version=reviewer.standards_version,
                    supports_individual_review=reviewer.supports_individual_review,
                    supports_requirement_set_review=reviewer.supports_requirement_set_review,
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


def _overall_from_statuses(statuses: list[ReviewStatus]) -> ReviewStatus:
    if any(status == ReviewStatus.UNACCEPTABLE for status in statuses):
        return ReviewStatus.UNACCEPTABLE
    if any(status == ReviewStatus.REVISION_RECOMMENDED for status in statuses):
        return ReviewStatus.REVISION_RECOMMENDED
    return ReviewStatus.ACCEPTABLE
