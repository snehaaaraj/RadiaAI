import { afterEach, describe, expect, it, vi } from 'vitest';
import { AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';

const getAccessToken = vi.fn<() => Promise<string | null>>();

vi.mock('@/auth/msal', () => ({
  getAccessToken: () => getAccessToken(),
}));

const { default: apiClient } = await import('./client');

type RequestHandler = (config: InternalAxiosRequestConfig) => Promise<InternalAxiosRequestConfig>;

function runRequestInterceptors(): Promise<InternalAxiosRequestConfig> {
  const handlers = (
    apiClient.interceptors.request as unknown as { handlers: { fulfilled: RequestHandler }[] }
  ).handlers;
  const config = { headers: new AxiosHeaders() } as InternalAxiosRequestConfig;
  return handlers.reduce(
    (pending, handler) => pending.then(handler.fulfilled),
    Promise.resolve(config)
  );
}

describe('apiClient auth header', () => {
  afterEach(() => getAccessToken.mockReset());

  it('attaches the Entra access token as a bearer token', async () => {
    getAccessToken.mockResolvedValue('token-123');

    const config = await runRequestInterceptors();

    expect(config.headers.Authorization).toBe('Bearer token-123');
    expect(config.headers['X-Request-ID']).toEqual(expect.any(String));
  });

  it('sends no Authorization header when sign-in is disabled', async () => {
    getAccessToken.mockResolvedValue(null);

    const config = await runRequestInterceptors();

    expect(config.headers.Authorization).toBeUndefined();
  });
});
