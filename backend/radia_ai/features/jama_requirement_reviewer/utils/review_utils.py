"""Utility functions for review status aggregation and processing."""

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    ReviewCompletion,
    ReviewCompletionStatus,
    ReviewFailureReason,
    ReviewStatus,
)


def overall_from_statuses(statuses: list[ReviewStatus]) -> ReviewStatus:
    """
    Aggregate multiple review statuses into a single overall status.

    Priority order:
    1. NOT_EVALUATED - only when every status is NOT_EVALUATED, so a batch where
       nothing could be reviewed is never reported as acceptable
    2. UNACCEPTABLE - if any status is UNACCEPTABLE, the overall is UNACCEPTABLE
    3. REVISION_RECOMMENDED - if any status is REVISION_RECOMMENDED, the overall is
       REVISION_RECOMMENDED
    4. ACCEPTABLE - only if all remaining statuses are ACCEPTABLE

    An empty list aggregates to ACCEPTABLE: there was nothing to object to.
    """
    if statuses and all(status == ReviewStatus.NOT_EVALUATED for status in statuses):
        return ReviewStatus.NOT_EVALUATED
    if any(status == ReviewStatus.UNACCEPTABLE for status in statuses):
        return ReviewStatus.UNACCEPTABLE
    if any(status == ReviewStatus.REVISION_RECOMMENDED for status in statuses):
        return ReviewStatus.REVISION_RECOMMENDED
    return ReviewStatus.ACCEPTABLE


def aggregate_completions(completions: list[ReviewCompletion]) -> ReviewCompletion:
    """
    Combine per-item completion records into one record for a batch review.

    - nothing reviewed, or every item complete -> COMPLETE
    - every item failed                        -> FAILED, keeping the first cause
    - some items failed                        -> PARTIAL, reporting the counts
    """
    failed = [item for item in completions if not item.is_complete]
    if not failed:
        return ReviewCompletion.complete()

    first_reason = failed[0].reason or ReviewFailureReason.REVIEW_ENGINE_UNAVAILABLE

    if len(failed) == len(completions):
        # Every item failed for (typically) the same reason — surface it directly.
        return ReviewCompletion(
            status=ReviewCompletionStatus.FAILED,
            reason=first_reason,
            message=failed[0].message,
        )

    return ReviewCompletion.partial(
        reason=first_reason,
        failed_count=len(failed),
        total_count=len(completions),
    )
