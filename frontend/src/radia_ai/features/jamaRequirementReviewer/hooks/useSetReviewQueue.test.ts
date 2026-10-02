import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { reviewRequirement } from '@/radia_ai/features/jamaRequirementReviewer/api/review';
import {
  formatSetReviewError,
  useSetReviewQueue,
} from './useSetReviewQueue';
import { extractErrorInfo } from '@/utils/errorInfo';
import type { RequirementReviewResponse } from '@/types/api';

vi.mock('@/radia_ai/features/jamaRequirementReviewer/api/review', () => ({
  reviewRequirement: vi.fn(),
}));

const successfulReview: RequirementReviewResponse = {
  review_id: 'review-1',
  overall: 'Acceptable',
  completion: { status: 'complete', reason: null, message: '' },
  category_results: [],
  findings: [],
  determinism: {
    reviewer_bundle_version: '1',
    prompt_versions: {},
    standards_versions: {},
    config_hash: '',
    config_snapshot: { temperature: 0, max_tokens: 0, retrieval_top_k: 0 },
  },
};

const queueItem = {
  key: '0:REQ-1',
  payload: { requirement_id: 'REQ-1', text: 'Requirement text' },
};

beforeEach(() => {
  vi.clearAllMocks();
});

function asItemError(raw: unknown) {
  return { ...extractErrorInfo(raw), raw };
}

describe('formatSetReviewError', () => {
  it('surfaces the backend code and message from a structured ErrorResponse', () => {
    const raw = {
      success: false,
      error: {
        code: 'LLM_ERROR',
        message: 'Azure OpenAI deployment "gpt-4o" is not available',
        detail: { http_status: 503 },
      },
      request_id: 'abc-123',
    };
    expect(formatSetReviewError(asItemError(raw))).toBe(
      'LLM_ERROR: Azure OpenAI deployment "gpt-4o" is not available [HTTP 503]'
    );
  });

  it('expands validation errors into per-field reasons', () => {
    const raw = {
      success: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Request validation failed',
        detail: {
          errors: [
            { loc: ['body', 'text'], msg: 'String should have at least 10 characters' },
          ],
        },
      },
      request_id: 'r1',
    };
    expect(formatSetReviewError(asItemError(raw))).toBe(
      'VALIDATION_ERROR: Request validation failed - text: String should have at least 10 characters'
    );
  });

  it('truncates long validation error lists', () => {
    const raw = {
      success: false,
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Request validation failed',
        detail: {
          errors: Array.from({ length: 5 }, (_, i) => ({ loc: ['body', `f${i}`], msg: 'bad' })),
        },
      },
      request_id: '',
    };
    expect(formatSetReviewError(asItemError(raw))).toContain('(+2 more)');
  });

  it('includes the upstream cause for wrapped Azure errors', () => {
    const raw = {
      success: false,
      error: {
        code: 'LLM_ERROR',
        message: 'AI model call failed',
        detail: { original_error: 'rate limit exceeded, retry after 12s' },
      },
      request_id: '',
    };
    expect(formatSetReviewError(asItemError(raw))).toBe(
      'LLM_ERROR: AI model call failed - rate limit exceeded, retry after 12s'
    );
  });

  it('keeps the real message for a thrown Error', () => {
    expect(formatSetReviewError(asItemError(new TypeError('fetch failed')))).toBe(
      'TypeError: fetch failed'
    );
  });

  it('never produces an empty or placeholder-only reason', () => {
    expect(formatSetReviewError(asItemError(undefined))).toBe('An unexpected error occurred');
    expect(formatSetReviewError(asItemError({}))).toBe('An unexpected error occurred');
  });
});

describe('useSetReviewQueue', () => {
  it('retries a failed requirement once and records the successful retry', async () => {
    vi.mocked(reviewRequirement)
      .mockRejectedValueOnce(new Error('temporary failure'))
      .mockResolvedValueOnce(successfulReview);
    const { result } = renderHook(() => useSetReviewQueue());

    await act(async () => {
      await result.current.runSingle(queueItem);
    });

    expect(reviewRequirement).toHaveBeenCalledTimes(2);
    expect(result.current.statuses[queueItem.key]).toEqual({
      state: 'done',
      result: successfulReview,
    });
  });

  it('retries once when the review response reports a failed completion', async () => {
    vi.mocked(reviewRequirement)
      .mockResolvedValueOnce({
        ...successfulReview,
        completion: {
          status: 'failed',
          reason: 'llm_call_failed',
          message: 'The model call failed.',
        },
      })
      .mockResolvedValueOnce(successfulReview);
    const { result } = renderHook(() => useSetReviewQueue());

    await act(async () => {
      await result.current.runSingle(queueItem);
    });

    expect(reviewRequirement).toHaveBeenCalledTimes(2);
    expect(result.current.statuses[queueItem.key]).toEqual({
      state: 'done',
      result: successfulReview,
    });
  });

  it('records the error after the one automatic retry also fails', async () => {
    vi.mocked(reviewRequirement)
      .mockRejectedValueOnce(new Error('first failure'))
      .mockRejectedValueOnce(new Error('second failure'));
    const { result } = renderHook(() => useSetReviewQueue());

    await act(async () => {
      await result.current.runSingle(queueItem);
    });

    expect(reviewRequirement).toHaveBeenCalledTimes(2);
    expect(result.current.statuses[queueItem.key]?.state).toBe('error');
    expect(result.current.statuses[queueItem.key]?.error?.message).toBe('second failure');
  });
});
