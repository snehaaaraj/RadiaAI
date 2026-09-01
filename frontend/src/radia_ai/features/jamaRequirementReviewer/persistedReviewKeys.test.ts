import { afterEach, describe, expect, it } from 'vitest';
import {
  DELTA_REVIEW_RESULT_KEY,
  purgeLegacyReviewResults,
  REQUIREMENT_REVIEW_RESULT_KEY,
} from './persistedReviewKeys';

describe('persisted review result keys', () => {
  afterEach(() => {
    localStorage.clear();
  });

  it('uses the current schema version for each review type', () => {
    expect(REQUIREMENT_REVIEW_RESULT_KEY).toBe('requirement-review-result-v2');
    expect(DELTA_REVIEW_RESULT_KEY).toBe('delta-review-result-v2');
  });

  it('purges unversioned results without deleting current results', () => {
    localStorage.setItem('requirement-review-result', '{"legacy":true}');
    localStorage.setItem('delta-review-result', '{"legacy":true}');
    localStorage.setItem(REQUIREMENT_REVIEW_RESULT_KEY, '{"current":true}');
    localStorage.setItem(DELTA_REVIEW_RESULT_KEY, '{"current":true}');

    purgeLegacyReviewResults();

    expect(localStorage.getItem('requirement-review-result')).toBeNull();
    expect(localStorage.getItem('delta-review-result')).toBeNull();
    expect(localStorage.getItem(REQUIREMENT_REVIEW_RESULT_KEY)).toBe('{"current":true}');
    expect(localStorage.getItem(DELTA_REVIEW_RESULT_KEY)).toBe('{"current":true}');
  });
});
