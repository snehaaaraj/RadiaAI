import type { FindingSeverity, ReviewFinding, ReviewStatus } from '@/types/api';

const SEVERITY_PENALTY: Record<FindingSeverity, number> = {
  Low: 0.5,
  Medium: 1.25,
  High: 2,
  Critical: 3,
};
const STATUS_BASE_SCORE: Record<ReviewStatus, number> = {
  Acceptable: 9.5,
  'Revision Recommended': 6.5,
  Unacceptable: 3,
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function getReviewQualityScore(
  overall: ReviewStatus,
  findings: ReviewFinding[]
): number {
  if (findings.length === 0) {
    return overall === 'Acceptable' ? 10 : overall === 'Revision Recommended' ? 7 : 4;
  }

  const penalty = findings.reduce((total, finding) => total + SEVERITY_PENALTY[finding.severity], 0);
  let score = 10 - penalty;

  if (overall === 'Acceptable') {
    score = Math.max(score, 8.5);
  } else if (overall === 'Revision Recommended') {
    score = clamp(score, 4, 8.5);
  } else {
    score = clamp(score, 0, 4);
  }

  return Number(clamp(score, 0, 10).toFixed(1));
}

export function getReviewQualityColor(score: number): string {
  const pct = clamp(score, 0, 10) / 10;
  const hue = Math.round(120 * pct);
  return `hsl(${hue} 80% 46%)`;
}

export function getCategoryStatusScore(status: ReviewStatus): number {
  return STATUS_BASE_SCORE[status];
}
