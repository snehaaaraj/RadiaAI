"""Requirement-set reviewer with deterministic set-level checks."""

from __future__ import annotations

from collections import Counter

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


class RequirementSetReviewer(RequirementReviewer):
    name = "requirement_set"
    reviewer_version = "1.0.0"
    prompt_version = "requirement-set.v1"
    standards_version = "internal-standards.v1"
    supports_individual_review = False
    supports_requirement_set_review = True

    def review_requirement(self, payload: RequirementReviewInput) -> ReviewerResult:
        return ReviewerResult(
            reviewer=self.name,
            reviewer_version=self.reviewer_version,
            prompt_version=self.prompt_version,
            standards_version=self.standards_version,
            overall=ReviewStatus.ACCEPTABLE,
            findings=[],
        )

    def review_requirement_set(self, payload: RequirementSetReviewInput) -> ReviewerResult:
        findings: list[ReviewFinding] = []
        requirements = payload.requirements
        text_to_ids: dict[str, list[str]] = {}
        for req in requirements:
            normalized = _normalize_text(req.text)
            if normalized not in text_to_ids:
                text_to_ids[normalized] = []
            text_to_ids[normalized].append(req.requirement_id or "<missing-id>")

        duplicate_groups = [ids for ids in text_to_ids.values() if len(ids) > 1]
        if duplicate_groups:
            findings.append(
                ReviewFinding(
                    category="Duplicate Requirements",
                    reviewer=self.name,
                    severity=FindingSeverity.HIGH,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.UNACCEPTABLE,
                    rule="Requirement set shall not contain duplicate requirements.",
                    explanation=(
                        "Identical normalized requirement text was detected for multiple IDs."
                    ),
                    evidence=f"Duplicate groups: {duplicate_groups}",
                    recommendation=(
                        "Remove duplicates or consolidate into a single canonical requirement."
                    ),
                    reference="INCOSE",
                )
            )

        overlap_pairs = _find_overlaps(requirements)
        if overlap_pairs:
            findings.append(
                ReviewFinding(
                    category="Overlapping Requirements",
                    reviewer=self.name,
                    severity=FindingSeverity.MEDIUM,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.REVISION_RECOMMENDED,
                    rule="Requirement set should avoid overlapping requirement scope.",
                    explanation="Pairs with high lexical overlap were detected.",
                    evidence=f"Overlaps: {overlap_pairs}",
                    recommendation="Clarify boundaries and remove overlapping obligation scope.",
                    reference="Internal Engineering Standards",
                )
            )

        contradiction_pairs = _find_simple_contradictions(requirements)
        if contradiction_pairs:
            findings.append(
                ReviewFinding(
                    category="Contradictory Requirements",
                    reviewer=self.name,
                    severity=FindingSeverity.HIGH,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.UNACCEPTABLE,
                    rule="Requirement set shall not contain contradictory statements.",
                    explanation=(
                        "Conflicting directional terms were detected for matching subjects."
                    ),
                    evidence=f"Contradictions: {contradiction_pairs}",
                    recommendation=(
                        "Resolve contradiction and retain a single consistent requirement."
                    ),
                    reference="INCOSE",
                )
            )

        missing_parent = [
            req.requirement_id or "<missing-id>"
            for req in requirements
            if req.metadata.get("parent_id", "").strip() == ""
        ]
        if missing_parent:
            findings.append(
                ReviewFinding(
                    category="Missing Parent Requirements",
                    reviewer=self.name,
                    severity=FindingSeverity.MEDIUM,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.REVISION_RECOMMENDED,
                    rule="Derived requirements should include parent trace linkage.",
                    explanation="Requirements are missing parent linkage metadata.",
                    evidence=f"Missing parent_id: {missing_parent}",
                    recommendation="Add parent requirement links for traceability completeness.",
                    reference="Traceability Guide",
                )
            )

        missing_verification_method = [
            req.requirement_id or "<missing-id>"
            for req in requirements
            if req.metadata.get("verification_method", "").strip() == ""
        ]
        if missing_verification_method:
            findings.append(
                ReviewFinding(
                    category="Missing Verification Methods",
                    reviewer=self.name,
                    severity=FindingSeverity.MEDIUM,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.REVISION_RECOMMENDED,
                    rule="Each requirement should include a verification method.",
                    explanation="Verification method metadata is missing.",
                    evidence=f"Missing verification_method: {missing_verification_method}",
                    recommendation=(
                        "Populate verification method (test, analysis, inspection, or "
                        "demonstration)."
                    ),
                    reference="Verification Planning Standard",
                )
            )

        naming_conflicts = _find_naming_inconsistencies(requirements)
        if naming_conflicts:
            findings.append(
                ReviewFinding(
                    category="Naming Consistency",
                    reviewer=self.name,
                    severity=FindingSeverity.LOW,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.REVISION_RECOMMENDED,
                    rule="Requirement IDs and naming prefixes should be consistent.",
                    explanation="Multiple ID prefix styles were detected in the same set.",
                    evidence=f"Prefix counts: {naming_conflicts}",
                    recommendation=(
                        "Standardize requirement ID naming conventions per project rules."
                    ),
                    reference="Company Style Guide",
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


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def _tokenize_for_overlap(text: str) -> set[str]:
    return {token.strip(".,;:()[]") for token in text.lower().split() if len(token) > 3}


def _find_overlaps(requirements: list[RequirementReviewInput]) -> list[tuple[str, str]]:
    overlaps: list[tuple[str, str]] = []
    for index, left in enumerate(requirements):
        left_tokens = _tokenize_for_overlap(left.text)
        left_id = left.requirement_id or "<missing-id>"
        for right in requirements[index + 1 :]:
            right_tokens = _tokenize_for_overlap(right.text)
            right_id = right.requirement_id or "<missing-id>"
            union_size = len(left_tokens | right_tokens)
            if union_size == 0:
                continue
            similarity = len(left_tokens & right_tokens) / union_size
            if similarity >= 0.8:
                overlaps.append((left_id, right_id))
    return overlaps


def _find_simple_contradictions(
    requirements: list[RequirementReviewInput],
) -> list[tuple[str, str]]:
    positive_terms = {"enable", "allow", "include", "increase"}
    negative_terms = {"disable", "prevent", "exclude", "decrease"}
    contradictions: list[tuple[str, str]] = []

    for index, left in enumerate(requirements):
        left_text = left.text.lower()
        left_id = left.requirement_id or "<missing-id>"
        for right in requirements[index + 1 :]:
            right_text = right.text.lower()
            right_id = right.requirement_id or "<missing-id>"
            shared_subject = (
                left_text.split(" shall ")[0].strip()
                == right_text.split(" shall ")[0].strip()
            )
            left_positive = any(term in left_text for term in positive_terms)
            left_negative = any(term in left_text for term in negative_terms)
            right_positive = any(term in right_text for term in positive_terms)
            right_negative = any(term in right_text for term in negative_terms)
            if shared_subject and (
                (left_positive and right_negative)
                or (left_negative and right_positive)
            ):
                contradictions.append((left_id, right_id))
    return contradictions


def _find_naming_inconsistencies(requirements: list[RequirementReviewInput]) -> dict[str, int]:
    prefixes = [
        req.requirement_id.split("-")[0]
        for req in requirements
        if req.requirement_id and "-" in req.requirement_id
    ]
    prefix_counts = Counter(prefixes)
    if len(prefix_counts) <= 1:
        return {}
    return dict(prefix_counts)


def _overall_from_findings(findings: list[ReviewFinding]) -> ReviewStatus:
    if any(f.status == ReviewStatus.UNACCEPTABLE for f in findings):
        return ReviewStatus.UNACCEPTABLE
    if any(f.status == ReviewStatus.REVISION_RECOMMENDED for f in findings):
        return ReviewStatus.REVISION_RECOMMENDED
    return ReviewStatus.ACCEPTABLE
