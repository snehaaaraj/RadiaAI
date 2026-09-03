import type { ReviewCompletion, ReviewFailureReason } from '@/types/api';

/**
 * Helpers for reading the review completion record.
 *
 * A review result can reach the UI without a completion record — it was persisted
 * in localStorage by an earlier build, or came from an older backend. Those are
 * treated as complete, which matches how they were rendered at the time. Every
 * read goes through `resolveCompletion` so a missing record can never throw.
 */

export const DEFAULT_COMPLETION: ReviewCompletion = {
  status: 'complete',
  reason: null,
  message: '',
};

export function resolveCompletion(completion?: ReviewCompletion | null): ReviewCompletion {
  return completion ?? DEFAULT_COMPLETION;
}

/** True when the review engine did not evaluate the subject at all. */
export function isReviewFailed(completion?: ReviewCompletion | null): boolean {
  return resolveCompletion(completion).status === 'failed';
}

/** True when only some items in a batch were evaluated. */
export function isReviewPartial(completion?: ReviewCompletion | null): boolean {
  return resolveCompletion(completion).status === 'partial';
}

/** True for anything other than a fully completed review. */
export function isReviewIncomplete(completion?: ReviewCompletion | null): boolean {
  return resolveCompletion(completion).status !== 'complete';
}

const FAILURE_TITLES: Record<ReviewFailureReason, string> = {
  review_engine_unavailable: 'Review engine unavailable',
  no_standards_context: 'No matching standards found',
  retrieval_failed: 'Standards retrieval failed',
  llm_call_failed: 'AI review did not complete',
  invalid_llm_response: 'AI response could not be read',
};

const FALLBACK_TITLE = 'Review did not complete';
const PARTIAL_TITLE = 'Review only partly completed';

/** Short heading for the incomplete-review notice. */
export function getCompletionTitle(completion?: ReviewCompletion | null): string {
  const resolved = resolveCompletion(completion);
  if (resolved.status === 'partial') return PARTIAL_TITLE;
  if (resolved.reason) return FAILURE_TITLES[resolved.reason] ?? FALLBACK_TITLE;
  return FALLBACK_TITLE;
}

const FALLBACK_MESSAGE =
  'The review did not finish, so no findings are available for this requirement.';

/** Explanatory body text, falling back when the backend sent no message. */
export function getCompletionMessage(completion?: ReviewCompletion | null): string {
  const resolved = resolveCompletion(completion);
  return resolved.message || FALLBACK_MESSAGE;
}

/**
 * Whether re-running the review is a sensible next step.
 *
 * Transient failures are worth retrying. A missing standards library is not —
 * the user has to ingest documents first.
 */
export function isRetryableFailure(completion?: ReviewCompletion | null): boolean {
  const { reason } = resolveCompletion(completion);
  return (
    reason === 'retrieval_failed' ||
    reason === 'llm_call_failed' ||
    reason === 'invalid_llm_response'
  );
}
