import { describe, expect, it } from 'vitest';
import type { ReviewCompletion, ReviewFailureReason } from '@/types/api';
import {
  getCompletionMessage,
  getCompletionTitle,
  isReviewFailed,
  isReviewIncomplete,
  isReviewPartial,
  isRetryableFailure,
  resolveCompletion,
} from './reviewCompletion';
import { getReviewQualityScore } from './reviewQuality';

function failed(reason: ReviewFailureReason, message = 'Something went wrong.'): ReviewCompletion {
  return { status: 'failed', reason, message };
}

const COMPLETE: ReviewCompletion = { status: 'complete', reason: null, message: '' };
const PARTIAL: ReviewCompletion = {
  status: 'partial',
  reason: 'llm_call_failed',
  message: '1 of 2 requirements could not be evaluated.',
};

describe('resolveCompletion', () => {
  it('treats a missing record as complete so old persisted results still render', () => {
    expect(resolveCompletion(undefined).status).toBe('complete');
    expect(resolveCompletion(null).status).toBe('complete');
  });

  it('passes through a provided record unchanged', () => {
    const completion = failed('retrieval_failed');
    expect(resolveCompletion(completion)).toBe(completion);
  });
});

describe('status predicates', () => {
  it('identifies a failed review', () => {
    expect(isReviewFailed(failed('llm_call_failed'))).toBe(true);
    expect(isReviewFailed(COMPLETE)).toBe(false);
    expect(isReviewFailed(PARTIAL)).toBe(false);
  });

  it('identifies a partial review', () => {
    expect(isReviewPartial(PARTIAL)).toBe(true);
    expect(isReviewPartial(COMPLETE)).toBe(false);
  });

  it('treats both failed and partial as incomplete', () => {
    expect(isReviewIncomplete(PARTIAL)).toBe(true);
    expect(isReviewIncomplete(failed('no_standards_context'))).toBe(true);
    expect(isReviewIncomplete(COMPLETE)).toBe(false);
  });

  it('does not flag a missing record as incomplete', () => {
    expect(isReviewIncomplete(undefined)).toBe(false);
  });
});

describe('notice copy', () => {
  it('names the specific failure cause', () => {
    expect(getCompletionTitle(failed('no_standards_context'))).toBe('No matching standards found');
    expect(getCompletionTitle(failed('review_engine_unavailable'))).toBe(
      'Review engine unavailable'
    );
  });

  it('uses a partial-specific title', () => {
    expect(getCompletionTitle(PARTIAL)).toBe('Review only partly completed');
  });

  it('falls back when no reason is present', () => {
    expect(getCompletionTitle({ status: 'failed', reason: null, message: '' })).toBe(
      'Review did not complete'
    );
  });

  it('prefers the backend message', () => {
    expect(getCompletionMessage(failed('llm_call_failed', 'Azure timed out.'))).toBe(
      'Azure timed out.'
    );
  });

  it('falls back to explanatory copy when the message is empty', () => {
    expect(getCompletionMessage(failed('llm_call_failed', ''))).toContain('did not finish');
  });
});

describe('isRetryableFailure', () => {
  it('offers retry for transient failures', () => {
    expect(isRetryableFailure(failed('retrieval_failed'))).toBe(true);
    expect(isRetryableFailure(failed('llm_call_failed'))).toBe(true);
    expect(isRetryableFailure(failed('invalid_llm_response'))).toBe(true);
  });

  it('does not offer retry when the user must act first', () => {
    // Retrying cannot help until standards are ingested or Azure is configured.
    expect(isRetryableFailure(failed('no_standards_context'))).toBe(false);
    expect(isRetryableFailure(failed('review_engine_unavailable'))).toBe(false);
  });
});

describe('getReviewQualityScore', () => {
  it('never scores an unevaluated review as a pass', () => {
    // The regression this contract exists to prevent: a failed review reading 10/10.
    expect(getReviewQualityScore('Not Evaluated', [])).toBe(0);
  });

  it('still scores a genuinely clean review as a pass', () => {
    expect(getReviewQualityScore('Acceptable', [])).toBe(10);
  });
});
