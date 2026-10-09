/**
 * Microsoft Entra ID (MSAL) configuration for the SPA.
 *
 * Sign-in is enabled only when the client ID, tenant ID, and API scope are all
 * provided at build time. Without them the app runs unauthenticated, which the
 * backend accepts only in its local/test environments.
 */

export const authSettings = {
  clientId: import.meta.env.VITE_ENTRA_CLIENT_ID?.trim() ?? '',
  tenantId: import.meta.env.VITE_ENTRA_TENANT_ID?.trim() ?? '',
  apiScope: import.meta.env.VITE_ENTRA_API_SCOPE?.trim() ?? '',
  redirectUri: import.meta.env.VITE_ENTRA_REDIRECT_URI?.trim() || window.location.origin,
};

export function isLocalViewingEnvironment(mode: string, isDev: boolean, hostname: string): boolean {
  return (
    isDev &&
    mode === 'local-preview' &&
    ['localhost', '127.0.0.1', '::1'].includes(hostname)
  );
}

export const isLocalViewing = isLocalViewingEnvironment(
  import.meta.env.MODE,
  import.meta.env.DEV,
  window.location.hostname
);

export const isAuthEnabled = Boolean(
  !isLocalViewing &&
    authSettings.clientId &&
    authSettings.tenantId &&
    authSettings.apiScope
);

/** Scopes requested for the Radia API access token. */
export const apiTokenRequest = { scopes: [authSettings.apiScope] };
