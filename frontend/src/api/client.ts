/**
 * Axios HTTP client instance.
 *
 * All API modules import this instance rather than calling axios directly.
 * This centralises:
 *   - Base URL configuration
 *   - Default headers
 *   - Request ID injection
 *   - TODO: Auth token injection (Entra ID)
 *   - Error response normalisation
 */

import axios, { AxiosError, type AxiosResponse } from 'axios';
import type { ErrorResponse } from '@/types/api';
import { API_BASE } from '@/utils/constants';

/** Generate a UUID v4 for request tracing */
function generateRequestId(): string {
  return crypto.randomUUID();
}

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120_000, // 2 minutes
});

// ---------------------------------------------------------------------------
// Request interceptor - inject tracing header and auth token
// ---------------------------------------------------------------------------

apiClient.interceptors.request.use((config) => {
  // Attach a unique ID to every outbound request for distributed tracing
  config.headers['X-Request-ID'] = generateRequestId();

  // TODO: Inject Entra ID bearer token here, e.g.:
  // const token = await getAccessToken();
  // config.headers['Authorization'] = `Bearer ${token}`;

  return config;
});

// ---------------------------------------------------------------------------
// Response interceptor - normalise errors
// ---------------------------------------------------------------------------

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<ErrorResponse>) => {
    const status = error.response?.status;
    const data = error.response?.data;

    // Surface the backend's structured error so callers get consistent shape
    if (data && typeof data === 'object' && 'error' in data && data.error) {
      return Promise.reject({
        ...data,
        error: {
          ...data.error,
          detail: { ...data.error.detail, ...(status ? { http_status: status } : {}) },
        },
      } satisfies ErrorResponse);
    }

    // The server responded, but not with our structured envelope (gateway HTML,
    // proxy error, plain-text body). Keep whatever the server actually said.
    if (error.response) {
      const body = typeof data === 'string' ? data : data ? JSON.stringify(data) : '';
      const snippet = body.trim().slice(0, 300);
      return Promise.reject({
        success: false,
        error: {
          code: status === 429 ? 'RATE_LIMITED' : 'HTTP_ERROR',
          message: `HTTP ${status} ${error.response.statusText || ''}`.trim() +
            (snippet ? ` - ${snippet}` : ''),
          detail: { http_status: status, body: snippet },
        },
        request_id: (error.config?.headers?.['X-Request-ID'] as string) ?? '',
      } satisfies ErrorResponse);
    }

    // No response at all - network failure, timeout, or request cancelled.
    const isTimeout = error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT';
    return Promise.reject({
      success: false,
      error: {
        code: isTimeout ? 'TIMEOUT_ERROR' : 'NETWORK_ERROR',
        message: isTimeout
          ? `Request timed out after ${Math.round((error.config?.timeout ?? 0) / 1000)}s without a response from the server`
          : error.message || 'A network error occurred',
        detail: { axios_code: error.code ?? null, url: error.config?.url ?? null },
      },
      request_id: (error.config?.headers?.['X-Request-ID'] as string) ?? '',
    } satisfies ErrorResponse);
  }
);

export default apiClient;
