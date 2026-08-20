"""Utility functions for review status aggregation and processing."""

from radia_ai.features.jama_requirement_reviewer.models.review_models import ReviewStatus


def overall_from_statuses(statuses: list[ReviewStatus]) -> ReviewStatus:
    """
    Aggregate multiple review statuses into a single overall status.

    Priority order:
    1. UNACCEPTABLE - if any status is UNACCEPTABLE, the overall is UNACCEPTABLE
    2. REVISION_RECOMMENDED - if any status is REVISION_RECOMMENDED, the overall is REVISION_RECOMMENDED
    3. ACCEPTABLE - only if all statuses are ACCEPTABLE
    """
    if any(status == ReviewStatus.UNACCEPTABLE for status in statuses):
        return ReviewStatus.UNACCEPTABLE
    if any(status == ReviewStatus.REVISION_RECOMMENDED for status in statuses):
        return ReviewStatus.REVISION_RECOMMENDED
    return ReviewStatus.ACCEPTABLE
