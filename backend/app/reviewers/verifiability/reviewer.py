"""Verifiability reviewer with deterministic rule checks."""

from __future__ import annotations

import re

from app.models.review_models import (
    FindingSeverity,
    PassFail,
    RequirementReviewInput,
    ReviewerResult,
    ReviewFinding,
    ReviewStatus,
)
from app.reviewers.base import RequirementReviewer
from app.rules.verifiability_rules import OPERATING_CONDITION_HINTS, UNMEASURABLE_TERMS


class VerifiabilityReviewer(RequirementReviewer):
    name = "verifiability"
    reviewer_version = "1.0.0"
    prompt_version = "verifiability.v1"
    standards_version = "incose.v1"
    supports_individual_review = True

    def review_requirement(self, payload: RequirementReviewInput) -> ReviewerResult:
        text = payload.text.strip()
        lower_text = text.lower()
        findings: list[ReviewFinding] = []

        has_number = bool(re.search(r"\b\d+(\.\d+)?\b", text))
        found_unmeasurable = sorted({term for term in UNMEASURABLE_TERMS if term in lower_text})
        if not has_number and found_unmeasurable:
            findings.append(
                ReviewFinding(
                    category="Missing Quantitative Limits",
                    reviewer=self.name,
                    severity=FindingSeverity.HIGH,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.UNACCEPTABLE,
                    rule="Requirement shall include measurable acceptance criteria.",
                    explanation="Unmeasurable adjectives are present without quantitative limits.",
                    evidence=f"Unmeasurable terms: {', '.join(found_unmeasurable)}",
                    recommendation="Replace qualitative terms with numeric acceptance thresholds.",
                    reference="INCOSE",
                )
            )

        has_operating_condition = any(hint in lower_text for hint in OPERATING_CONDITION_HINTS)
        if not has_operating_condition:
            findings.append(
                ReviewFinding(
                    category="Operating Conditions",
                    reviewer=self.name,
                    severity=FindingSeverity.MEDIUM,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.REVISION_RECOMMENDED,
                    rule="Requirement should identify operating conditions or context.",
                    explanation="No operating condition cue words were detected.",
                    evidence=text,
                    recommendation="Add context such as environmental/mission condition bounds.",
                    reference="EARS",
                )
            )

        if not has_number:
            findings.append(
                ReviewFinding(
                    category="Verifiability",
                    reviewer=self.name,
                    severity=FindingSeverity.MEDIUM,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.REVISION_RECOMMENDED,
                    rule="Requirement should be directly testable and verifiable.",
                    explanation="No numeric test threshold was detected.",
                    evidence=text,
                    recommendation=(
                        "Add measurable values, tolerances, or explicit pass/fail criteria."
                    ),
                    reference="INCOSE",
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


def _overall_from_findings(findings: list[ReviewFinding]) -> ReviewStatus:
    if any(f.status == ReviewStatus.UNACCEPTABLE for f in findings):
        return ReviewStatus.UNACCEPTABLE
    if any(f.status == ReviewStatus.REVISION_RECOMMENDED for f in findings):
        return ReviewStatus.REVISION_RECOMMENDED
    return ReviewStatus.ACCEPTABLE
