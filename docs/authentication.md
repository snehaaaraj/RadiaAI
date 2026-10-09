# Authentication and authorization

Radia AI uses **Microsoft Entra ID single sign-on** for the app and **per-user
linked Jama accounts** for everything that touches Jama. Every API endpoint is
protected by default. Only the health probes and the Microsoft Graph webhook
receiver are public, and the receiver authenticates each notification by its
subscription secret.

## How it works

```
Browser (MSAL)                   Radia API                          Jama Connect
───────────────                  ─────────                          ────────────
Sign in with Microsoft  ──►  Bearer <Entra access token>
                             • RS256 signature (tenant JWKS)
                             • issuer, audience, exp/nbf, tenant
                             • scope access_as_user
                             • app role Radia.*
                             │
                             ├─ /jama/*  ──► decrypt *this user's* Jama
                             │               API credentials ──────────►  OAuth client-credentials
                             │                                            token for that user;
                             │                                            Jama enforces their own
                             │                                            project permissions
                             └─ review history stored with owner id
```

### Why Jama needs a one-time link

Jama Connect has **no OAuth authorization-code ("Sign in with Jama") flow**.
Its REST API does not accept Microsoft or SAML sessions, even when the Jama web
UI uses Entra SSO, and it has no service-account impersonation. The only
Jama-supported way to act *as the individual user* is the user's own API
credentials, created in Jama under **profile → Set API Credentials**. Each user:

1. Signs in to Radia with Microsoft (no extra password).
2. Opens **Settings → Jama account**, creates API credentials in Jama, and
   pastes the client ID and secret once.
3. Radia exchanges them for a token, calls `GET /rest/v1/users/current`,
   checks that the Jama email or username matches the Microsoft sign-in
   (`JAMA_REQUIRE_EMAIL_MATCH`), and stores them encrypted.

From then on, every Jama request runs as that user. Jama itself decides which
projects they can read or write, and Jama's audit trail shows the real person.
If the user revokes the credentials in Jama, Radia returns
`JAMA_CREDENTIALS_INVALID` and the UI asks them to re-link.

The shared service account (`JAMA_USERNAME`/`JAMA_PASSWORD` or
`JAMA_CLIENT_ID`/`JAMA_CLIENT_SECRET`) is used **only** when `ENVIRONMENT` is
`local` or `test`. It is never used in a deployed environment.

### Credential storage

- Encrypted with Fernet (AES-128-CBC + HMAC-SHA256) using
  `JAMA_CREDENTIAL_ENCRYPTION_KEY`.
- Stored one blob per user in a dedicated private container
  (`JAMA_CREDENTIAL_CONTAINER_NAME`, default `radia-user-secrets`), separate
  from the document container, so ingestion can never read it. Blob names are a
  SHA-256 of the user's tenant and object id.
- The ciphertext embeds the owner's identity and is verified on decrypt, so a
  blob copied to another user's name is useless.
- Secrets are never returned by the API or logged.
- **Key rotation:** set `JAMA_CREDENTIAL_ENCRYPTION_KEY=<new>,<old>`. New links
  use the first key, and existing links still decrypt with the old one. Remove
  the old key once users have re-linked. Links encrypted only with a removed
  key behave as "not linked".

## Roles

Roles are Entra **app roles** on the API app registration. Assign them to users
or, preferably, security groups under *Enterprise applications → Radia AI API →
Users and groups*.

| App role value        | Grants                                                                                   |
|-----------------------|------------------------------------------------------------------------------------------|
| `Radia.User`          | Chat, search, standards, documents (read), run reviews, own review history, own Jama link |
| `Radia.DocumentAdmin` | `Radia.User` plus ingestion trigger/upload/job status, webhook re-subscribe, delete indexed documents |
| `Radia.Admin`         | Everything, including every user's review history and dispositions                       |

A signed-in user with no Radia role gets `403` (`ENTRA_REQUIRE_APP_ROLE=true`).
For a second layer, also set **Assignment required = Yes** on the enterprise
application.

### Endpoint protection

| Endpoint                                   | Requirement                                   |
|--------------------------------------------|-----------------------------------------------|
| `GET /health/live`, `/health/ready`        | Public (load balancer probes)                 |
| `POST /ingest/webhook`                     | Public; Graph `clientState` + persisted subscription check |
| `GET /auth/me`                             | `Radia.User`                                  |
| `/chat`, `/search`, `/standards`, `/documents` (GET), `/review/*`, `/ingest/status` | `Radia.User` |
| `/jama/*` (including `/jama/account`)      | `Radia.User` + the user's own linked Jama account |
| `POST /ingest`, `/ingest/upload`, `GET /ingest/jobs/{id}`, `POST /ingest/webhook/subscribe`, `DELETE /documents/{id}` | `Radia.DocumentAdmin` |
| `GET /review/history` (all users)          | `Radia.Admin`; others only see their own      |

Protection is applied when routers are mounted in
[router.py](../backend/app/api/v1/router.py), so a new endpoint is protected
by default.

## Entra ID setup

Create **two app registrations** in the company tenant.

### 1. API app registration (`Radia AI API`)

1. *Expose an API*: set the Application ID URI to `api://<api-client-id>` and
   add the delegated scope **`access_as_user`** (admins and users can consent).
2. *App roles*: create `Radia.User`, `Radia.DocumentAdmin`, and `Radia.Admin`
   (allowed member types: Users/Groups).
3. *Manifest*: set `"requestedAccessTokenVersion": 2` (v1 tokens are accepted
   too).
4. *Enterprise application → Users and groups*: assign roles to groups.

### 2. SPA app registration (`Radia AI Web`)

1. *Authentication → Single-page application*: add the redirect URIs, for
   example `http://localhost:5173`, the Vercel URL, and later the internal URL
   (such as `https://radia.corp.local`).
2. *API permissions*: add **Radia AI API → access_as_user** and grant admin
   consent.

### Environment variables

Backend (`.env` or host environment):

| Variable | Purpose |
|----------|---------|
| `ENTRA_TENANT_ID` | Company tenant ID |
| `ENTRA_CLIENT_ID` | **API** app registration client ID |
| `ENTRA_AUDIENCE` | Optional; defaults to `api://<ENTRA_CLIENT_ID>` (the bare client ID is also accepted) |
| `ENTRA_REQUIRED_SCOPE` | Default `access_as_user` |
| `ENTRA_REQUIRE_APP_ROLE` | Default `true` |
| `ENTRA_ALLOW_APP_TOKENS` | Default `false`; allow client-credentials tokens that carry Radia roles (automation) |
| `JAMA_BASE_URL` | Jama instance URL |
| `JAMA_CREDENTIAL_ENCRYPTION_KEY` | Fernet key(s). Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and store it as a secret (Vercel env var, Key Vault, or root-only file on Linux) |
| `JAMA_REQUIRE_EMAIL_MATCH` | Default `true` |
| `ALLOWED_ORIGIN_REGEX` | CORS regex; defaults to `*.vercel.app` previews. Set to an empty value for internal hosting |

Frontend (build-time, `VITE_*`):

| Variable | Purpose |
|----------|---------|
| `VITE_ENTRA_CLIENT_ID` | **SPA** app registration client ID |
| `VITE_ENTRA_TENANT_ID` | Company tenant ID |
| `VITE_ENTRA_API_SCOPE` | `api://<api-client-id>/access_as_user` |
| `VITE_ENTRA_REDIRECT_URI` | Optional; defaults to the page origin |

When the `VITE_ENTRA_*` variables are absent, the SPA skips sign-in. The
backend accepts that only with `ENVIRONMENT=local` or `test`.

For a local UI preview that skips Microsoft sign-in even when frontend Entra
settings are present, run the frontend with `npm run dev:local` from
`frontend/`. This `local-preview` mode is enabled only by Vite's development server on
`localhost`, `127.0.0.1`, or `::1`; production builds and other hosts continue
to require the configured sign-in. API requests still follow the backend's
authentication configuration, so unauthenticated API access requires its
existing local/test auth bypass to be enabled.

## Behaviour by environment

| `ENVIRONMENT` | Entra not configured | Shared Jama service account |
|---------------|----------------------|-----------------------------|
| `local`, `test` | Synthetic local user with `LOCAL_DEV_USER_ROLES` (default `Radia.Admin`) | Allowed when an unlinked user calls Jama and Entra is not configured |
| `development` | Every protected request returns `503 AUTH_NOT_CONFIGURED` | Never |
| `staging`, `production`, or **unset** | **Startup fails** | Never |

`ENVIRONMENT` defaults to `production`, so a deployment that forgets to set it
fails closed instead of enabling the local bypass. Set `ENVIRONMENT=local` in
your local `.env`.

## Deployment notes

### Vercel (current)

- Set the backend env vars in the backend Vercel project and the `VITE_*` vars
  in the frontend project, then redeploy (Vite inlines them at build time).
- Add the production and preview URLs as SPA redirect URIs.
  Preview URLs change per deployment, so either use a stable preview alias or
  sign in only on the production URL.
- Signing keys are cached per serverless instance (`ENTRA_JWKS_CACHE_TTL_SECONDS`).

### Internal Linux host behind the VPN (planned)

- Set `ALLOWED_ORIGINS` to the internal URL and leave `ALLOWED_ORIGIN_REGEX`
  empty.
- Users' browsers must reach `login.microsoftonline.com`, which normal Entra
  SSO already requires.
- The **backend host** needs outbound HTTPS to
  `login.microsoftonline.com` (signing keys), the Jama instance, and Azure.
  `httpx` honours `HTTPS_PROXY` and `NO_PROXY` when a corporate proxy is used.
  If signing keys can't be fetched and none are cached, the API returns
  `503 AUTH_PROVIDER_UNAVAILABLE`. Once fetched, keys keep working through
  short outages.
- Add the internal URL as an SPA redirect URI. Nothing else changes, because
  per-user Jama credentials and history stay in the same Blob Storage account.
- Keep `JAMA_CREDENTIAL_ENCRYPTION_KEY` out of the repo: use a systemd
  `EnvironmentFile` readable only by the service user, or Azure Key Vault.

## Error codes

| Code | HTTP | Meaning / UI action |
|------|------|---------------------|
| `AUTHENTICATION_REQUIRED` | 401 | Missing, invalid, or expired token. MSAL refreshes it or redirects to sign-in |
| `FORBIDDEN` | 403 | Missing Radia role, or role insufficient for the action |
| `AUTH_NOT_CONFIGURED` | 503 | Deployed environment without Entra settings (fail closed) |
| `AUTH_PROVIDER_UNAVAILABLE` | 503 | Entra signing keys unreachable |
| `JAMA_ACCOUNT_NOT_LINKED` | 403 | Prompt the user to link Jama in Settings |
| `JAMA_CREDENTIALS_INVALID` | 403 | Linked credentials revoked or wrong. Prompt to re-link |
| `JAMA_ACCOUNT_MISMATCH` | 403 | Submitted credentials belong to someone else |
| `JAMA_PERMISSION_DENIED` | 403 | Jama denied this user access to the project or item |

## Upgrade notes

- **Review history is now private per user.** Entries created before this
  change have no owner and are visible to `Radia.Admin` only. They also expire
  under the existing 10-day retention.
- `reviewer_id` in disposition requests is ignored. The reviewer is always the
  signed-in user.
- `python-jose` was replaced by `PyJWT[crypto]`.
