/**
 * Normalises unknown rejection values into the structured error shape the
 * backend returns, so both visual components and background workers report the
 * same code, message, detail and request id.
 */

import type { ErrorResponse } from '@/types/api';

export interface ExtractedErrorInfo {
  code: string;
  message: string;
  detail: Record<string, unknown>;
  requestId: string;
}

export function extractErrorInfo(error: unknown): ExtractedErrorInfo {
  // Structured ErrorResponse from backend (see api/client.ts interceptor)
  if (error && typeof error === 'object' && 'error' in error) {
    const errorResponse = error as ErrorResponse;
    if (errorResponse.error && typeof errorResponse.error === 'object') {
      return {
        code: errorResponse.error.code || 'UNKNOWN_ERROR',
        message: errorResponse.error.message || 'An unexpected error occurred',
        detail: errorResponse.error.detail ?? {},
        requestId: errorResponse.request_id ?? '',
      };
    }
  }

  // Thrown Error instance - keep its real message and name.
  if (error instanceof Error) {
    return {
      code: error.name && error.name !== 'Error' ? error.name : 'UNKNOWN_ERROR',
      message: error.message || 'An unexpected error occurred',
      detail: error.stack ? { stack: error.stack } : {},
      requestId: '',
    };
  }

  // Generic error-like object with a message
  if (error && typeof error === 'object' && 'message' in error) {
    return {
      code: 'UNKNOWN_ERROR',
      message: String((error as { message: unknown }).message),
      detail: {},
      requestId: '',
    };
  }

  if (typeof error === 'string' && error.trim()) {
    return { code: 'UNKNOWN_ERROR', message: error, detail: {}, requestId: '' };
  }

  return {
    code: 'UNKNOWN_ERROR',
    message: 'An unexpected error occurred',
    detail: {},
    requestId: '',
  };
}
