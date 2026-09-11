"""Utility functions for review completion aggregation."""

from radia_ai.features.jama_requirement_reviewer.models.review_models import (
    ReviewCompletion,
    ReviewCompletionStatus,
    ReviewFailureReason,
)


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
        # Every item failed for (typically) the same reason - surface it directly.
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
