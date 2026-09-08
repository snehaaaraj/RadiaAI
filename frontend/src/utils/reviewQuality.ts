import type { CategoryResult, ReviewStatus } from '@/types/api';

const STATUS_BASE_SCORE: Record<ReviewStatus, number> = {
  Acceptable: 9.5,
  'Revision Recommended': 6.5,
  Unacceptable: 3,
  // An unevaluated subject has no quality score. Callers should check the review
  // completion record and render the incomplete notice instead of a score; this
  // entry only keeps the lookup total.
  'Not Evaluated': 0,
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/**
 * Overall score: the mean of the scored category scores.
 *
 * The overall number answers "how good is this requirement overall", so it is
 * the average of the parts shown in the category grid and nothing else. It is
 * deliberately NOT clamped by the worst category — that would make the headline
 * number disagree with the tiles directly beneath it.
 *
 * Severity is not applied again here. The backend already maps a finding's
 * severity to its status (Low/Medium -> Revision Recommended, High/Critical ->
 * Unacceptable) and a category takes the worst status among its findings, so
 * severity is fully reflected in the category scores being averaged. Penalising
 * it a second time would double-count it.
 *
 * The gating verdict still travels separately as the overall `status` chip, so
 * a requirement that averages well but is Unacceptable in one category is not
 * presented as passing.
 */
export function getReviewQualityScore(categories: CategoryResult[]): number {
  const scored = categories.filter((category) => category.status !== 'Not Evaluated');

  // Nothing was scored — never fall through to a passing value.
  if (scored.length === 0) return 0;

  const total = scored.reduce(
    (sum, category) => sum + getCategoryStatusScore(category.status),
    0
  );

  // Category scores land on quarter/eighth values, so keep three decimals to
  // hold the exact mean (e.g. 7.875). Display rounds to one decimal.
  return Number((clamp(total / scored.length, 0, 10)).toFixed(3));
}

export function getReviewQualityColor(score: number): string {
  const pct = clamp(score, 0, 10) / 10;
  const hue = Math.round(120 * pct);
  return `hsl(${hue} 80% 46%)`;
}

export function getCategoryStatusScore(status: ReviewStatus): number {
  return STATUS_BASE_SCORE[status];
}
