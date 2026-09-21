import type { CategoryResult, ReviewStatus } from '@/types/api';

/**
 * Fallback score per status, used only for payloads that carry no numeric
 * `score` (older stored reviews). Live reviews score each category from its
 * findings on the backend, so these values are a compatibility shim and not the
 * scoring model.
 */
const STATUS_FALLBACK_SCORE: Record<ReviewStatus, number> = {
  Acceptable: 10,
  'Revision Recommended': 6.5,
  Unacceptable: 3,
  // An unevaluated subject has no quality score. Callers should check the review
  // completion record and render the incomplete notice instead of a score; this
  // entry only keeps the lookup total.
  'Not Evaluated': 0,
};

/** At or above this average score the subject is Acceptable. */
export const ACCEPTABLE_THRESHOLD = 8;
/** At or above this average score the subject needs revision; below it, Unacceptable. */
export const REVISION_THRESHOLD = 5;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Overall score: the mean of the scored category scores.
 *
 * The overall number answers "how good is this requirement overall", so it is
 * the average of the parts shown in the category grid and nothing else. It is
 * deliberately NOT clamped by the worst category — that would make the headline
 * number disagree with the tiles directly beneath it, and would condemn an
 * otherwise strong requirement over a single weak sub-category.
 *
 * Severity is not applied again here. The backend already turns each finding's
 * severity into the category score being averaged, so penalising it a second
 * time would double-count it.
 */
export function getReviewQualityScore(categories: CategoryResult[]): number {
  const scored = categories.filter((category) => category.status !== 'Not Evaluated');

  // Nothing was scored — never fall through to a passing value.
  if (scored.length === 0) return 0;

  const total = scored.reduce((sum, category) => sum + getCategoryScore(category), 0);

  // Category scores can land on fractional values, so keep three decimals to
  // hold the exact mean (e.g. 7.875). Display rounds to one decimal.
  return Number(clamp(total / scored.length, 0, 10).toFixed(3));
}

/**
 * Verdict band for an average score.
 *
 * Bands come from the average, so a single weak sub-category lowers the overall
 * score without on its own forcing an Unacceptable verdict.
 */
export function getReviewQualityStatus(score: number): ReviewStatus {
  if (score >= ACCEPTABLE_THRESHOLD) return 'Acceptable';
  if (score >= REVISION_THRESHOLD) return 'Revision Recommended';
  return 'Unacceptable';
}

export function getReviewQualityColor(score: number): string {
  const pct = clamp(score, 0, 10) / 10;
  const hue = Math.round(120 * pct);
  return `hsl(${hue} 80% 46%)`;
}

/**
 * Score for one category: the backend's finding-derived value when present,
 * otherwise a status-based approximation for legacy payloads.
 */
export function getCategoryScore(category: CategoryResult): number {
  if (typeof category.score === 'number' && Number.isFinite(category.score)) {
    return clamp(category.score, 0, 10);
  }
  return getCategoryStatusScore(category.status);
}

export function getCategoryStatusScore(status: ReviewStatus): number {
  return STATUS_FALLBACK_SCORE[status];
}

