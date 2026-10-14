/// <reference types="vite/client" />

/** Release version, injected by Vite from backend/app/VERSION. */
declare const __APP_VERSION__: string;

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  /** Application (client) ID of the Radia SPA app registration. */
  readonly VITE_ENTRA_CLIENT_ID?: string;
  /** Directory (tenant) ID of the company Entra tenant. */
  readonly VITE_ENTRA_TENANT_ID?: string;
  /** Delegated API scope, e.g. api://<api-client-id>/access_as_user. */
  readonly VITE_ENTRA_API_SCOPE?: string;
  /** Optional redirect URI; defaults to the current origin. */
  readonly VITE_ENTRA_REDIRECT_URI?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
