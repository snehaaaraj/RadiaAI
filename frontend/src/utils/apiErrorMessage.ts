import type { ErrorResponse } from '@/types/api';

type ErrorWithMessage = {
  message?: unknown;
};

type ErrorWithResponseMessage = {
  error?: {
    message?: unknown;
  };
};

export function getApiErrorMessage(error: unknown, fallback = 'A network error occurred'): string {
  if (error && typeof error === 'object') {
    const errorWithResponse = error as ErrorWithResponseMessage;
    if (typeof errorWithResponse.error?.message === 'string' && errorWithResponse.error.message.trim()) {
      return errorWithResponse.error.message;
    }

    const errorWithMessage = error as ErrorWithMessage;
    if (typeof errorWithMessage.message === 'string' && errorWithMessage.message.trim()) {
      return errorWithMessage.message;
    }
  }

  const networkError = error as ErrorResponse | undefined;
  if (typeof networkError?.error?.message === 'string' && networkError.error.message.trim()) {
    return networkError.error.message;
  }

  return fallback;
}
