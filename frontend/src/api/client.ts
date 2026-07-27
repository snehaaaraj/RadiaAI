/**
 * Axios HTTP client instance.
 *
 * All API modules import this instance rather than calling axios directly.
 * This centralises:
 *   - Base URL configuration
 *   - Default headers
 *   - Request ID injection
 *   - Auth token injection (Phase 2 — Entra ID)
 *   - Error response normalisation
 */

import axios, { AxiosError, type AxiosResponse } from 'axios';
import type { ErrorResponse } from '@/types/api';

/** Generate a UUID v4 for request tracing */
function generateRequestId(): string {
  return crypto.randomUUID();
}

const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30_000, // 30 seconds — LLM calls can be slow
});

// ---------------------------------------------------------------------------
// Request interceptor — inject tracing header and auth token
// ---------------------------------------------------------------------------

apiClient.interceptors.request.use((config) => {
  // Attach a unique ID to every outbound request for distributed tracing
  config.headers['X-Request-ID'] = generateRequestId();

  // Phase 2: Inject Entra ID bearer token here, e.g.:
  // const token = await getAccessToken();
  // config.headers['Authorization'] = `Bearer ${token}`;

  return config;
});

// ---------------------------------------------------------------------------
// Response interceptor — normalise errors
// ---------------------------------------------------------------------------

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<ErrorResponse>) => {
    // Surface the backend's structured error so callers get consistent shape
    if (error.response?.data) {
      return Promise.reject(error.response.data);
    }
    // Network error or timeout — normalise to ErrorResponse shape
    return Promise.reject({
      success: false,
      error: {
        code: 'NETWORK_ERROR',
        message: error.message || 'A network error occurred',
        detail: {},
      },
      request_id: '',
    } satisfies ErrorResponse);
  }
);

export default apiClient;
