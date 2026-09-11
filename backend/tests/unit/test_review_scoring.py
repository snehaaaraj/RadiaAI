"""
Unit tests for the numeric review scoring contract.

The guarantees under test:
- a category score is earned from its findings, never a constant per status;
- a flawless requirement can reach a full 10;
- the overall verdict comes from the *average* of the category scores, so one
  weak sub-category cannot single-handedly declare the review Unacceptable.
"""

import pytest
from tests.conftest import build_stub_finding

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    FindingSeverity,
    ReviewStatus,
)
from radia_ai.features.jama_requirement_reviewer.utils.review_scoring import (
    MAX_SCORE,
    average_score,
    score_from_findings,
    status_from_score,
)


def _finding(severity: FindingSeverity):
    return build_stub_finding(severity=severity)


# ---------------------------------------------------------------------------
# Category scores are earned, not looked up
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_findings_scores_a_perfect_ten() -> None:
    assert score_from_findings([]) == MAX_SCORE


@pytest.mark.unit
def test_score_decreases_monotonically_with_severity() -> None:
    scores = [
        score_from_findings([_finding(severity)])
        for severity in (
            FindingSeverity.LOW,
            FindingSeverity.MEDIUM,
            FindingSeverity.HIGH,
            FindingSeverity.CRITICAL,
        )
    ]
    assert scores == sorted(scores, reverse=True)
    assert len(set(scores)) == len(scores)


@pytest.mark.unit
def test_any_finding_drops_a_category_below_acceptable() -> None:
    """A category with an open finding must never present itself as clean."""
    assert status_from_score(score_from_findings([_finding(FindingSeverity.LOW)])) is (
        ReviewStatus.REVISION_RECOMMENDED
    )


@pytest.mark.unit
def test_repeat_findings_compound_but_with_diminishing_weight() -> None:
    one = score_from_findings([_finding(FindingSeverity.MEDIUM)])
    two = score_from_findings([_finding(FindingSeverity.MEDIUM)] * 2)

    assert two < one
    # The second finding costs half of the first, not the same again.
    assert MAX_SCORE - two == pytest.approx((MAX_SCORE - one) * 1.5)


@pytest.mark.unit
def test_score_never_goes_negative() -> None:
    assert score_from_findings([_finding(FindingSeverity.CRITICAL)] * 10) == 0.0


# ---------------------------------------------------------------------------
# Bands come from the average
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (10.0, ReviewStatus.ACCEPTABLE),
        (8.0, ReviewStatus.ACCEPTABLE),
        (7.99, ReviewStatus.REVISION_RECOMMENDED),
        (5.0, ReviewStatus.REVISION_RECOMMENDED),
        (4.99, ReviewStatus.UNACCEPTABLE),
        (0.0, ReviewStatus.UNACCEPTABLE),
    ],
)
def test_status_bands(score: float, expected: ReviewStatus) -> None:
    assert status_from_score(score) is expected


@pytest.mark.unit
def test_one_low_band_does_not_condemn_a_strong_requirement() -> None:
    """The regression this pins: a single 3.5 sub-category forced Unacceptable."""
    overall = average_score([10.0, 10.0, 10.0, 3.5])

    assert overall == pytest.approx(8.375)
    assert status_from_score(overall) is ReviewStatus.ACCEPTABLE


@pytest.mark.unit
def test_broadly_weak_categories_still_fail() -> None:
    """Averaging must not turn a genuinely bad requirement into a pass."""
    overall = average_score([4.0, 3.5, 2.0, 4.0])

    assert status_from_score(overall) is ReviewStatus.UNACCEPTABLE
