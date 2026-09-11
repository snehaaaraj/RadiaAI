"""
Numeric scoring for requirement reviews.

Scores are *earned* from the findings a review produced, not looked up from the
category a finding belongs to. Every category starts at a perfect ``10.0`` and
loses ground for each finding, weighted by severity, so a genuinely well-written
requirement can score 10 and two categories that both fail can still be told
apart by how badly they fail.

The verdict bands are derived from the score, and the overall verdict is derived
from the *average* of the category scores. One weak category therefore drags the
average down without single-handedly condemning an otherwise strong
requirement.
"""

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    FindingSeverity,
    ReviewFinding,
    ReviewStatus,
)

MAX_SCORE = 10.0
"""Score awarded to a category the review found nothing wrong with."""

ACCEPTABLE_THRESHOLD = 8.0
"""At or above this score the subject is Acceptable."""

REVISION_THRESHOLD = 5.0
"""At or above this score the subject needs revision; below it, it is Unacceptable."""

SEVERITY_PENALTY: dict[FindingSeverity, float] = {
    FindingSeverity.LOW: 2.5,
    FindingSeverity.MEDIUM: 4.0,
    FindingSeverity.HIGH: 6.0,
    FindingSeverity.CRITICAL: 8.0,
}
"""
Points deducted for the most severe finding in a category.

The Low penalty is deliberately large enough (10 - 2.5 = 7.5) that any finding
at all pushes a category below ``ACCEPTABLE_THRESHOLD``: a category with an open
finding must never present itself as clean. The High penalty likewise drops a
category below ``REVISION_THRESHOLD``, keeping the derived band consistent with
the severity-to-status mapping used elsewhere in the pipeline.
"""

REPEAT_PENALTY_WEIGHT = 0.5
"""
Weight applied to every finding after the most severe one.

Repeat problems in the same category compound, but with diminishing weight - the
first defect is what characterises the category, and full weight for each would
drive any multi-finding category straight to zero.
"""

_DEFAULT_PENALTY = SEVERITY_PENALTY[FindingSeverity.MEDIUM]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def score_from_findings(findings: list[ReviewFinding]) -> float:
    """
    Score a single category from its findings, on a 0-10 scale.

    No findings scores ``MAX_SCORE``. Otherwise the worst finding costs its full
    severity penalty and each additional finding costs ``REPEAT_PENALTY_WEIGHT``
    of its own.
    """
    if not findings:
        return MAX_SCORE

    penalties = sorted(
        (SEVERITY_PENALTY.get(finding.severity, _DEFAULT_PENALTY) for finding in findings),
        reverse=True,
    )
    deduction = penalties[0] + REPEAT_PENALTY_WEIGHT * sum(penalties[1:])
    return round(_clamp(MAX_SCORE - deduction, 0.0, MAX_SCORE), 3)


def status_from_score(score: float) -> ReviewStatus:
    """Map a 0-10 score onto the verdict band it falls in."""
    if score >= ACCEPTABLE_THRESHOLD:
        return ReviewStatus.ACCEPTABLE
    if score >= REVISION_THRESHOLD:
        return ReviewStatus.REVISION_RECOMMENDED
    return ReviewStatus.UNACCEPTABLE


def average_score(scores: list[float]) -> float:
    """
    Mean of the given scores, or ``MAX_SCORE`` when there is nothing to average.

    An empty list means nothing was found to object to; callers that must
    distinguish "nothing scored" from "nothing wrong" check completion state
    before scoring.
    """
    if not scores:
        return MAX_SCORE
    return round(sum(scores) / len(scores), 3)
