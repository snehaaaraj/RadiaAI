import { describe, expect, it } from 'vitest';
import { formatSetReviewError } from './useSetReviewQueue';
import { extractErrorInfo } from '@/utils/errorInfo';

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
