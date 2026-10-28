"""Bounded retry-with-backoff for rate-limited (HTTP 429) GET requests.

Every connector in this server only performs idempotent reads, so retrying is
safe as long as it is bounded: an unbounded retry loop against a
rate-limited upstream (Jama's environment-wide API budget, Atlassian Cloud's
per-site limits) would make the problem worse, not better.
"""

import asyncio
import random
from typing import Any

import httpx2

from mcp_radia.logging import get_logger

logger = get_logger(__name__)

#: Hard cap: the first attempt plus this many retries, never more.
MAX_RETRY_ATTEMPTS = 3
#: Base of the exponential backoff, in seconds.
_BASE_DELAY_SECONDS = 1.0
#: Upper bound on any single sleep, regardless of attempt number.
_MAX_DELAY_SECONDS = 8.0


def _retry_after_seconds(response: httpx2.Response) -> float | None:
    """Parse a ``Retry-After`` header expressed in seconds, if present and valid."""
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _backoff_seconds(attempt: int, response: httpx2.Response) -> float:
    """Delay before retrying ``attempt`` (1-based), honoring ``Retry-After`` when given."""
    retry_after = _retry_after_seconds(response)
    if retry_after is not None:
        return min(retry_after, _MAX_DELAY_SECONDS)
    exponential = _BASE_DELAY_SECONDS * (2.0 ** (attempt - 1))
    jitter = random.uniform(0, _BASE_DELAY_SECONDS)  # noqa: S311 (backoff jitter, not crypto)
    return float(min(exponential + jitter, _MAX_DELAY_SECONDS))


async def get_with_retry(
    client: httpx2.AsyncClient,
    url: str,
    *,
    system: str,
    operation: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    auth: httpx2.Auth | None = None,
) -> httpx2.Response:
    """GET ``url``, retrying a bounded number of times on HTTP 429.

    Returns the final response (status not yet checked) so the caller keeps
    owning ``raise_for_status``/error translation. Never retries on anything
    other than 429: other error statuses are the caller's to translate as-is,
    and retrying a non-idempotent failure mode would risk duplicating load
    against an already-struggling upstream.
    """
    attempt = 1
    while True:
        response = await client.get(url, params=params, headers=headers, auth=auth)
        if response.status_code != 429 or attempt >= MAX_RETRY_ATTEMPTS:
            return response
        delay = _backoff_seconds(attempt, response)
        logger.warning(
            "rate_limited_retry",
            system=system,
            operation=operation,
            attempt=attempt,
            delay_seconds=round(delay, 2),
        )
        await asyncio.sleep(delay)
        attempt += 1
