/**
 * Storage keys for persisted review results.
 *
 * The version suffix is bumped whenever the review response shape changes. A
 * result cached by an older build is then ignored rather than rendered against
 * the current UI — a payload saved before every category was scored would
 * otherwise draw a scorecard with categories silently missing.
 */
const RESULT_SCHEMA_VERSION = 'v2';

export const REQUIREMENT_REVIEW_RESULT_KEY = `requirement-review-result-${RESULT_SCHEMA_VERSION}`;
export const DELTA_REVIEW_RESULT_KEY = `delta-review-result-${RESULT_SCHEMA_VERSION}`;

/** Result keys written by builds that predate result-schema versioning. */
const LEGACY_RESULT_KEYS = ['requirement-review-result', 'delta-review-result'];

/** Drop results cached by an earlier schema so they cannot linger indefinitely. */
export function purgeLegacyReviewResults(): void {
  if (typeof window === 'undefined') return;
  for (const key of LEGACY_RESULT_KEYS) {
    window.localStorage.removeItem(key);
  }
}
