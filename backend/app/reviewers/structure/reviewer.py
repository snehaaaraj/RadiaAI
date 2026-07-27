"""Requirement structure reviewer with deterministic rule checks."""

from __future__ import annotations

from app.models.review_models import (
    FindingSeverity,
    PassFail,
    RequirementReviewInput,
    RequirementSetReviewInput,
    ReviewerResult,
    ReviewFinding,
    ReviewStatus,
)
from app.reviewers.base import RequirementReviewer
from app.rules.language_rules import SUBJECTIVE_WORDS
from app.rules.structure_rules import REQUIREMENT_LEVELS


class StructureReviewer(RequirementReviewer):
    name = "structure"
    reviewer_version = "1.0.0"
    prompt_version = "structure.v1"
    standards_version = "incose.v1"
    supports_individual_review = True
    supports_requirement_set_review = False

    def review_requirement(self, payload: RequirementReviewInput) -> ReviewerResult:
        text = payload.text.strip()
        lower_text = text.lower()
        findings: list[ReviewFinding] = []

        shall_count = lower_text.count(" shall ")
        if shall_count > 1:
            findings.append(
                ReviewFinding(
                    category="One Requirement per Statement",
                    reviewer=self.name,
                    severity=FindingSeverity.HIGH,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.UNACCEPTABLE,
                    rule="One requirement shall express one verifiable capability.",
                    explanation=(
                        "Multiple mandatory behaviors were detected in one requirement "
                        "statement."
                    ),
                    evidence=f"Detected {shall_count} uses of 'shall'.",
                    recommendation=(
                        "Split the statement into independent requirements, one behavior each."
                    ),
                    reference="INCOSE",
                )
            )

        found_subjective = sorted({word for word in SUBJECTIVE_WORDS if word in lower_text})
        if found_subjective:
            findings.append(
                ReviewFinding(
                    category="Human Judgment Language",
                    reviewer=self.name,
                    severity=FindingSeverity.MEDIUM,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.REVISION_RECOMMENDED,
                    rule="Requirement shall avoid subjective or human-judgment terms.",
                    explanation="Subjective wording prevents deterministic verification.",
                    evidence=f"Subjective terms: {', '.join(found_subjective)}",
                    recommendation="Replace subjective terms with objective measurable criteria.",
                    reference="Company Style Guide",
                )
            )

        if payload.requirement_level is None:
            findings.append(
                ReviewFinding(
                    category="Requirement Level",
                    reviewer=self.name,
                    severity=FindingSeverity.MEDIUM,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.REVISION_RECOMMENDED,
                    rule="Requirement shall declare its hierarchy level.",
                    explanation="Requirement level was not provided in review payload metadata.",
                    evidence="requirement_level missing",
                    recommendation=(
                        "Set requirement_level to aircraft, system, subsystem, or component."
                    ),
                    reference="Internal Engineering Standards",
                )
            )
        elif payload.requirement_level.lower() not in REQUIREMENT_LEVELS:
            findings.append(
                ReviewFinding(
                    category="Requirement Level",
                    reviewer=self.name,
                    severity=FindingSeverity.MEDIUM,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.REVISION_RECOMMENDED,
                    rule="Requirement shall use a supported hierarchy level.",
                    explanation=(
                        "Provided requirement level is not supported by current standards "
                        "registry."
                    ),
                    evidence=f"Provided requirement_level: {payload.requirement_level}",
                    recommendation="Use one of: aircraft, system, subsystem, component.",
                    reference="Internal Engineering Standards",
                )
            )

        overall = _overall_from_findings(findings)
        return ReviewerResult(
            reviewer=self.name,
            reviewer_version=self.reviewer_version,
            prompt_version=self.prompt_version,
            standards_version=self.standards_version,
            overall=overall,
            findings=findings,
        )

    def review_requirement_set(self, payload: RequirementSetReviewInput) -> ReviewerResult:
        return ReviewerResult(
            reviewer=self.name,
            reviewer_version=self.reviewer_version,
            prompt_version=self.prompt_version,
            standards_version=self.standards_version,
            overall=ReviewStatus.ACCEPTABLE,
            findings=[],
        )


def _overall_from_findings(findings: list[ReviewFinding]) -> ReviewStatus:
    if any(f.status == ReviewStatus.UNACCEPTABLE for f in findings):
        return ReviewStatus.UNACCEPTABLE
    if any(f.status == ReviewStatus.REVISION_RECOMMENDED for f in findings):
        return ReviewStatus.REVISION_RECOMMENDED
    return ReviewStatus.ACCEPTABLE
