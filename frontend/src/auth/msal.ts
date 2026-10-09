/**
 * MSAL client and access-token helpers shared by every API call.
 */

import {
  BrowserCacheLocation,
  EventType,
  InteractionRequiredAuthError,
  PublicClientApplication,
  type AccountInfo,
  type AuthenticationResult,
} from '@azure/msal-browser';
import { apiTokenRequest, authSettings, isAuthEnabled } from './authConfig';

export const msalInstance: PublicClientApplication | null = isAuthEnabled
  ? new PublicClientApplication({
      auth: {
        clientId: authSettings.clientId,
        authority: `https://login.microsoftonline.com/${authSettings.tenantId}`,
        redirectUri: authSettings.redirectUri,
        postLogoutRedirectUri: authSettings.redirectUri,
      },
      cache: {
        // Tokens live only for the browser tab; SSO with the Entra session restores them.
        cacheLocation: BrowserCacheLocation.SessionStorage,
      },
    })
  : null;

let redirecting = false;

/** Initialise MSAL and complete any sign-in redirect before the app renders. */
export async function initializeAuth(): Promise<void> {
  if (!msalInstance) return;
  const instance = msalInstance;
  await instance.initialize();
  const result = await instance.handleRedirectPromise();
  if (result?.account) {
    instance.setActiveAccount(result.account);
  } else if (!instance.getActiveAccount()) {
    const [account] = instance.getAllAccounts();
    if (account) instance.setActiveAccount(account);
  }
  instance.addEventCallback((event) => {
    if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
      const { account } = event.payload as AuthenticationResult;
      if (account) instance.setActiveAccount(account);
    }
  });
}

export function getActiveAccount(): AccountInfo | null {
  return msalInstance?.getActiveAccount() ?? null;
}

export async function signIn(): Promise<void> {
  if (!msalInstance || redirecting) return;
  redirecting = true;
  try {
    await msalInstance.loginRedirect(apiTokenRequest);
  } catch (error) {
    redirecting = false;
    throw error;
  }
}

export async function signOut(): Promise<void> {
  if (!msalInstance) return;
  await msalInstance.logoutRedirect({ account: msalInstance.getActiveAccount() ?? undefined });
}

/**
 * Return a Radia API access token, refreshing silently when needed.
 *
 * Returns null when sign-in is disabled. When Entra requires interaction
 * (expired session, new consent, MFA) the browser is redirected to sign in.
 */
export async function getAccessToken(): Promise<string | null> {
  if (!msalInstance) return null;
  const account = msalInstance.getActiveAccount();
  if (!account) return null;
  try {
    const result = await msalInstance.acquireTokenSilent({ ...apiTokenRequest, account });
    return result.accessToken;
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError && !redirecting) {
      redirecting = true;
      try {
        await msalInstance.acquireTokenRedirect({ ...apiTokenRequest, account });
      } catch {
        redirecting = false;
      }
    }
    throw error;
  }
}

/** Authorization header for requests made outside the shared axios client (e.g. SSE fetch). */
export async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
