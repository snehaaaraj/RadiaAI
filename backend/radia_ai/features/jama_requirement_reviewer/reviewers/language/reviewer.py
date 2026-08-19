"""Language reviewer with deterministic rule checks."""

from __future__ import annotations

import re

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    FindingSeverity,
    PassFail,
    RequirementReviewInput,
    ReviewerResult,
    ReviewFinding,
    ReviewStatus,
)
from radia_ai.features.jama_requirement_reviewer.reviewers.base import RequirementReviewer
from radia_ai.features.jama_requirement_reviewer.rules.language_rules import AMBIGUOUS_WORDS, BANNED_WORDS


class LanguageReviewer(RequirementReviewer):
    name = "language"
    reviewer_version = "1.0.0"
    prompt_version = "language.v1"
    standards_version = "incose.v1"
    supports_individual_review = True

    def review_requirement(self, payload: RequirementReviewInput) -> ReviewerResult:
        text = payload.text.strip()
        lower_text = text.lower()
        findings: list[ReviewFinding] = []

        has_shall = " shall " in f" {lower_text} "
        has_nonmandatory = any(
            token in f" {lower_text} " for token in (" should ", " will ", " may ")
        )
        if not has_shall and has_nonmandatory:
            rewrite = _replace_modal_with_shall(text)
            findings.append(
                ReviewFinding(
                    category="Requirement Language",
                    reviewer=self.name,
                    severity=FindingSeverity.HIGH,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.UNACCEPTABLE,
                    rule="Requirements shall use mandatory language ('shall').",
                    explanation=(
                        "The statement uses non-mandatory modal verbs without a mandatory "
                        "obligation."
                    ),
                    evidence=text,
                    recommendation="Rewrite requirement using 'shall' for mandatory behavior.",
                    reference="INCOSE",
                    suggested_rewrite=rewrite,
                )
            )

        found_banned = sorted({word for word in BANNED_WORDS if word in lower_text})
        if found_banned:
            rewrite = _remove_banned_words(text, found_banned)
            findings.append(
                ReviewFinding(
                    category="Banned Words",
                    reviewer=self.name,
                    severity=FindingSeverity.MEDIUM,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.REVISION_RECOMMENDED,
                    rule="Requirement shall not include banned or prohibited terms.",
                    explanation=(
                        "Banned words reduce precision and increase interpretation variance."
                    ),
                    evidence=f"Found banned words: {', '.join(found_banned)}",
                    recommendation="Replace banned terms with explicit, measurable wording.",
                    reference="Company Style Guide",
                    suggested_rewrite=rewrite,
                )
            )

        found_ambiguous = sorted({word for word in AMBIGUOUS_WORDS if word in lower_text})
        if found_ambiguous:
            rewrite = _flag_ambiguous_words(text, found_ambiguous)
            findings.append(
                ReviewFinding(
                    category="Ambiguous Wording",
                    reviewer=self.name,
                    severity=FindingSeverity.MEDIUM,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.REVISION_RECOMMENDED,
                    rule="Requirement shall avoid ambiguous wording.",
                    explanation="Ambiguous terms make verification and certification harder.",
                    evidence=f"Found ambiguous wording: {', '.join(found_ambiguous)}",
                    recommendation="Replace ambiguous words with objective measurable criteria.",
                    reference="EARS",
                    suggested_rewrite=rewrite,
                )
            )

        passive_match = re.search(r"\b(is|are|was|were|be|been|being)\s+(\w+ed)\b", lower_text)
        if passive_match:
            passive_phrase = passive_match.group(0)
            findings.append(
                ReviewFinding(
                    category="Passive Voice",
                    reviewer=self.name,
                    severity=FindingSeverity.LOW,
                    pass_fail=PassFail.FAIL,
                    status=ReviewStatus.REVISION_RECOMMENDED,
                    rule="Requirement should prefer active voice.",
                    explanation="Passive voice can hide actor responsibility.",
                    evidence=f"Passive construction detected: '{passive_phrase}'",
                    recommendation=(
                        "Rewrite sentence in active voice with a clear responsible subject."
                    ),
                    reference="INCOSE",
                    suggested_rewrite=(
                        "Identify the responsible system/actor and rewrite using active voice, e.g.:\n"
                        f"  The [system] shall [active verb] â€¦ (replacing '{passive_phrase}')"
                    ),
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


def _replace_modal_with_shall(text: str) -> str:
    """Replace the first non-mandatory modal with 'shall'."""
    result = re.sub(r'\bshould\b', 'shall', text, count=1, flags=re.IGNORECASE)
    result = re.sub(r'\bwill\b', 'shall', result, count=1, flags=re.IGNORECASE)
    result = re.sub(r'\bmay\b', 'shall', result, count=1, flags=re.IGNORECASE)
    return result


def _remove_banned_words(text: str, banned: list[str]) -> str:
    """Annotate each banned word with a placeholder indicating it needs replacement."""
    result = text
    for word in banned:
        result = re.sub(
            rf'\b{re.escape(word)}\b',
            f'[REPLACE: {word}]',
            result,
            flags=re.IGNORECASE,
        )
    return result


def _flag_ambiguous_words(text: str, ambiguous: list[str]) -> str:
    """Annotate each ambiguous word with a placeholder indicating it needs a measurable value."""
    result = text
    for word in ambiguous:
        result = re.sub(
            rf'\b{re.escape(word)}\b',
            f'[SPECIFY: {word}]',
            result,
            flags=re.IGNORECASE,
        )
    return result

