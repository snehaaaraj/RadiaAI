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

export const isAuthEnabled = Boolean(
  authSettings.clientId && authSettings.tenantId && authSettings.apiScope
);

/** Scopes requested for the Radia API access token. */
export const apiTokenRequest = { scopes: [authSettings.apiScope] };
