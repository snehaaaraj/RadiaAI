# Radia AI 2.0

AI-powered requirements engineering platform for aerospace and systems teams.
Radia AI reviews requirements against indexed standards, connects to a user's
Jama account for requirement import and approved Description write-back, and
provides grounded document search and chat.

The Chat page and floating chat window open at the latest message and follow new
responses automatically. Scroll up to pause following; use the down-arrow button
to smoothly scroll to the end of the conversation and resume automatic scrolling.
Reduced-motion preferences use an immediate scroll instead.

In Individual Requirement Review, the From Jama search text, selected requirement,
and project filter are retained when switching input tabs. Clear Review resets them.

---

## Architecture

For the current implementation and deployment details, see
[docs/architecture.md](docs/architecture.md). It distinguishes shipped
capabilities from optional, disabled integrations and features that remain
unimplemented.

```
┌────────────────────────────────────────────────────────────┐
│                         Frontend                           │
│      React + TypeScript + Vite + MUI + Framer Motion       │
│                    port 5173 (Vite dev server)             │
│                                                            │
│  src/pages/                         ← shared app pages     │
│  src/radia_ai/features/jamaRequirementReviewer/            │
│                                   ← reviewer feature UI    │
│  Jama requirement review, set review, delta review, history│
│  Jama Roundtrip page                ← reserved placeholder │
└──────────────────────┬─────────────────────────────────────┘
                       │  /api/v1/*
┌──────────────────────▼─────────────────────────────────────┐
│                          Backend                           │
│            FastAPI + Python 3.12 + Pydantic v2             │
│                       port 8000                            │
│                                                            │
│  LLM-based review pipeline:                                │
│    1. Retrieve standards (Azure AI Search)                 │
│    2. Review and score all four categories                 │
│    3. Synthesize and validate one recommendation           │
│    4. Resolve references and report completion status      │
│                                                            │
│  Ingestion API: persist job → Azure Storage Queue          │
│  Azure Functions worker: extract → chunk → embed → index   │
│    File-hash caching skips unchanged documents             │
│  Optional MCP client: live Jama reads in RadiaAI chat      │
└──────────┬──────────┬────────────────┬─────────────────────┘
           │          │                │
    ┌──────▼──┐ ┌─────▼──────┐ ┌──────▼──────┐
    │  Azure  │ │  Azure AI  │ │   Azure     │
    │ OpenAI  │ │   Search   │ │   Blob      │
    │ (GPT-5) │ │  (Vector)  │ │  Storage    │
    └─────────┘ └────────────┘ └─────────────┘
```

---

## Project Structure

```
backend/
  app/                         Shared API, auth, Azure clients, RAG, ingestion, MCP client
  radia_ai/features/
    jama_requirement_reviewer/ Review, Jama connector, history, synthesis, Skillz
    jama_roundtrip/            Reserved namespace; no roundtrip implementation
  tests/                       Unit and integration tests
  function_app.py              Azure Functions ingestion workers
  api/index.py                 Vercel FastAPI entry point
frontend/src/
  pages/                       Chat, search, documents, settings, landing
  radia_ai/features/
    jamaRequirementReviewer/   Review workflows and Jama integration UI
    jamaRoundtrip/             Reserved placeholder page
mcp-radia/                     Standalone MCP server; see its README
docs/                          Architecture, authentication, and error handling
infra/                         Azure deployment templates
```

---

## Review Pipeline

The review system uses **LLM-based architecture** with GPT-5 + RAG:

```
                        ┌─────────────────────────┐
    Input Requirement   │   LLM Review Pipeline   │
    ─────────────────►  │                         │
                        │  1. Normalize and embed │
                        │  2. Retrieve standards  │  ← Azure AI Search
                        │  3. Review + score      │  ← GPT-5, four categories
                        │  4. Synthesize and      │  ← validated recommendation
                        │     validate one        │
                        │     Description        │
                        └────────────┬────────────┘
                                     │
                              Enrich references
                              (SharePoint URLs)
                                     │
                                     ▼
                          Review Response (JSON)
```

**Key behaviors:**
- LLM analysis grounded in indexed standards documents
- All findings include a `suggested_rewrite` (full improved requirement text) that
  fixes only that finding; these are kept as supporting evidence
- A second synthesis step merges them into **one** `final_recommendation` - a
  replacement Description with per-finding provenance, conflict handling, and
  Skillz rules applied as the highest authority for aircraft-level requirements
  (see [docs/architecture.md](docs/architecture.md) §5.1-5.2)
- References point to actual SharePoint document URLs, not hardcoded names
- File-hash caching: unchanged documents are not re-embedded on restart
- Every response carries a **completion record** - a review that could not run
  reports `overall: "Not Evaluated"` plus the specific reason, so a failure is
  never presented as a clean requirement

### Review completion

Each response includes `completion: { status, reason, message }`.

| status | meaning |
|--------|---------|
| `complete` | the requirement was evaluated; an empty findings list means it passed |
| `partial` | batch review where only some requirements were evaluated |
| `failed` | nothing was evaluated; `reason` says why |

Failure reasons: `review_engine_unavailable`, `no_standards_context`,
`retrieval_failed`, `llm_call_failed`, `invalid_llm_response`.

---

## Ingestion Pipeline

Standards documents are queued from SharePoint on demand via `POST /api/v1/ingest`:

1. The API persists an ingestion job in Blob Storage and sends its job ID to Azure Storage Queue.
2. An Azure Functions queue-trigger worker downloads from SharePoint via Microsoft Graph API.
3. **Extract text** from validated PDF, DOCX, TXT, MD, CSV, JSON, and XML files.
4. **Chunk** into ~512-word overlapping segments.
5. **Embed** via Azure OpenAI text-embedding-3-large (3072 dimensions).
6. **Index** into Azure AI Search with vector + keyword + semantic search.
7. **Cache** file hashes - skip re-processing unchanged documents and make queue redelivery safe.

Single files can also be uploaded through `POST /api/v1/ingest/upload`. The API validates
the extension, MIME type and content before staging the bytes in Blob Storage. The default
maximum upload size is 4 MiB to stay within the Vercel request-body limit.

### Durable queue and job status

The FastAPI API runs on Vercel and only submits durable work; it does not run ingestion in
the request or use in-process background tasks. Deploy `backend/` as an Azure Functions
Python v2 app with the same `backend/requirements.txt` dependencies and configure:

- `AZURE_BLOB_CONNECTION_STRING` and `AZURE_BLOB_CONTAINER_NAME` (shared with the API)
- `AzureWebJobsStorage` (host coordination/timer storage; may point at the same account)
- `INGESTION_QUEUE_NAME` (same value in API and Functions; default `radia-ingestion`)
- `INGESTION_MAX_ATTEMPTS` (fixed at 5 to match the queue host's poison-message ceiling)
- `INGESTION_MAX_UPLOAD_BYTES` (default 4 MiB; maximum 4,500,000 bytes)
- the `AZURE_OPENAI_*`, `AZURE_SEARCH_*`, and `SHAREPOINT_*` settings used by the API

The Functions host configuration in `backend/host.json` allows up to 10 minutes per job,
retries failed queue messages up
to five deliveries with queue-trigger backoff and moves exhausted messages to
`<queue-name>-poison`. Per-job state
and failure details are durable in Blob Storage. The API returns a `job_id`; clients can
poll `GET /api/v1/ingest/jobs/{job_id}` for `queued`, `processing`, `retrying`, `completed`,
or `failed`. Supply an `Idempotency-Key` header when retrying the same API request; reuse
of that key with a different request returns HTTP 409. Document file hashes are also used
to make safe retries after partial indexing.

The Functions app also runs a two-minute recovery timer that redispatches jobs
whose Blob record was created but whose queue message was not submitted. This
covers the producer's brief Blob-write/Queue-send failure window.

Run the queue consumer locally from `backend/` with Azure Functions Core Tools using
`func start`. Storage Queue is created by the API on first submission; the configured
document Blob container must already exist.

### Automatic ingestion via SharePoint webhook (optional)

Instead of (or in addition to) clicking **Ingest Documents** on the Home page,
ingestion can be triggered automatically whenever a file in the SharePoint
standards folder is added, modified, or deleted. This uses a [Microsoft Graph
change-notification subscription](https://learn.microsoft.com/en-us/graph/api/resources/webhooks)
on the folder:

1. Graph POSTs a change notification to `POST /api/v1/ingest/webhook`
2. The `clientState` secret on the notification is verified against the
   subscription record stored in Blob Storage
3. The webhook validates every notification's `clientState`, subscription ID, and
   expected resource, then durably queues SharePoint ingestion. The queue worker
   re-scans SharePoint (file-hash caching still applies).

Because Graph subscriptions expire after a few days, the subscription is
renewed on API startup and by a throttled fallback check on `GET /api/v1/standards`
(which the frontend already makes on page load). Notifications are acknowledged
after queue submission without waiting for subscription-renewal network calls.

Enable it with `SHAREPOINT_WEBHOOK_ENABLED=true` and
`SHAREPOINT_WEBHOOK_PUBLIC_BASE_URL=https://<your-app-domain>` (see
`backend/.env.example`). `POST /api/v1/ingest/webhook/subscribe` can be called
to manually (re)create the subscription, e.g. after first enabling the feature.

**Seeing when ingestion completes:** the Home page polls the returned job ID at
`GET /api/v1/ingest/jobs/{job_id}` while work is queued or running. It also polls
`GET /api/v1/ingest/status` every 30 seconds and shows a "Last ingested"
chip next to the system status indicator, noting how long ago it ran, whether
it was triggered automatically (`auto (SharePoint change)`) or manually, and
the processed/failed counts. This works for both the webhook and the manual
button, so there's always a single place to check ingestion health.

---

## Functional Coverage

### Requirements review workflow

- [x] Upload or copy/paste requirement content
- [x] AI-powered review across 4 categories (language, structure, verifiability, certification)
- [x] Color-coded overall scoring
- [x] Sub-category scoring displayed directly below overall score, with every
      category scored on a completed review - a clean category reads as a pass,
      not as "not evaluated"
- [x] Persistent review state across navigation with explicit **Clear Review**
- [x] Findings grounded in indexed standards with source document links
- [x] Explicit reporting when a review could not run, with the reason and a retry
      action for transient failures

### AI-assisted modification workflow

- [x] AI-generated suggested changes from findings
- [x] One final recommended Description synthesized from every valid suggestion,
      ready to replace the original Jama Description
  - [x] Skillz rules (SharePoint) as the highest authority for aircraft-level
        requirements, enforced in code
  - [x] Duplicates merged, Skillz-overridden suggestions and unresolved conflicts
        kept visible with their reasons
  - [x] Original vs recommended diff, follow-ups, and cited Skillz rule text
- [x] Supporting evidence for every individual suggestion:
  - [x] What should change (recommendation)
  - [x] Source-of-truth standard reference with direct SharePoint link
  - [x] Supporting evidence/context for each finding
  - [x] The individual suggested rewrite

### Delta (verification) review workflow

- [x] Baseline vs updated comparison with a new/modified/deleted change summary
- [x] Requirements without an ID are paired by position, so pasting an original
      and its revision reads as one **modified** requirement rather than an
      unrelated add plus delete
- [x] Only changed requirements are re-scored; each is compared against the
      baseline text it replaces
- [x] Scoring only - no rewrites are proposed, because the requirement under
      review has already been revised
- [x] Read-only findings explaining what a category still leaves unmet

### Set review workflow

- [x] Parse a PDF containing multiple requirements and review each requirement
      independently
- [x] Show each requirement's score, findings, evidence, and final recommendation
- [x] Report partial completion when only some requirements could be reviewed

### Jama-connected review workflow

- [x] Link a user's own Jama API credentials; credentials are encrypted at rest
- [x] Search projects and requirements visible to that user's Jama account and
      import a requirement into an individual review
- [x] Save an explicit decision on the synthesized recommendation
- [x] Write the approved Description back to the reviewed Jama item, either using
      the recommendation or reviewer-modified text; rejected recommendations
      cannot be written
- [x] Detect a Jama item changed since review before writing, and record
      successful writes in review history

This guarded write-back is part of the requirement-review workflow. The separate
**Jama Roundtrip** page is still a placeholder; it does not provide bulk
roundtrip, synchronization, or reporting.

### Review history and workspace

- [x] Persist reviews, finding dispositions, recommendation decisions, and Jama
      write records in Blob Storage (10-day retention)
- [x] Keep user history private; administrators can review all users' history
- [x] Export review reports to PDF
- [x] Personalize theme, accent color, density, motion, sidebar, start page, and
      review-completion sound

### Search and chat

- [x] Search indexed documents using keyword, vector, or hybrid retrieval
- [x] Ask grounded questions with citations, using standard JSON or streamed SSE
- [x] Optionally switch a conversation to live Jama MCP tools; document RAG and
      live engineering-data answers are kept in separate conversation modes
- [x] Show indexed document metadata/chunks and let administrators remove
      indexed content without deleting the SharePoint source

The MCP chat integration is disabled by default. Jira and Confluence tools are
available in the standalone MCP server but are not enabled in Radia AI chat.

### Document ingestion

- [x] On-demand sync from SharePoint via `POST /api/v1/ingest`
- [x] Automatic sync via optional Microsoft Graph webhook when SharePoint documents change
- [x] Manual upload via API endpoint
- [x] File-hash deduplication (skip unchanged)
- [x] PDF, DOCX, TXT, MD, CSV, JSON, and XML text extraction
- [x] Hybrid search (keyword + vector + semantic)
- [x] Paginated document inventory, document details with indexed chunks, and
      administrator-only removal of indexed content (source files are unchanged)
- [x] Grounded chat with citations, including streamed answers

---

## Quick Start

### Prerequisites

- Node.js 22.13+ or 24+ (for local frontend development; see `frontend/package.json`)
- Python 3.12+ (for local backend development)
- Azure subscription with: Azure OpenAI (GPT-5 + text-embedding-3-large), Azure AI Search, Azure Blob Storage
- Microsoft Entra tenant and API/SPA app registrations for signed-in deployments
- Azure Functions Core Tools if running the durable ingestion worker locally
- SharePoint and Jama configuration for those integrations; both are optional for local startup

### 1. Clone and configure

```bash
git clone <repo-url>
cd RadiaAi-2.0
```

Backend and frontend each keep their own env files:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your Azure credentials

cp frontend/.env.example frontend/.env
# Edit frontend/.env if you need Microsoft sign-in locally (optional)
```

For a deployed backend environment, set the production values directly in your
hosting provider's environment variable settings (e.g. Vercel Project Settings
-> Environment Variables), using `backend/.env.example` as the reference for
which variables exist. For a deployed frontend build, use
`frontend/.env.production.example` instead - see its header for the stricter
production requirements.

### 2. Local backend development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .                # Install in editable mode
uvicorn radia_ai.main:app --reload --port 8000
```

On start, the server creates/updates the Azure AI Search index.

Standards are **not** ingested at startup - that keeps cold starts viable on
serverless hosting. Populate the index once via `POST /api/v1/ingest` (or the UI
button); file-hash caching means unchanged documents are skipped on later runs.

The review pipeline needs a populated index: with an empty index every review
returns `no_standards_context` instead of findings.

### 3. Local frontend development

Use Node.js 24 (recommended), or Node.js 22.13 or newer within the 22.x release
line. Node.js 20 is not supported by the current PDF dependency.

```bash
cd frontend
npm ci --include=dev
npm run start
      # starts Vite dev server on :5173, proxies /api to :8000
```

Run npm commands inside `frontend`; the repository root is not an npm package.
`npm ci` installs the versions recorded in `frontend/package-lock.json`.
`npm install` (or `npm i`) also installs the declared dependencies, but may update
the lockfile within the version ranges in `frontend/package.json`. Commit both
files when changing dependencies. Build, lint, and test commands require the
development dependencies; do not omit them before building.

### 4. Frontend deployment to Vercel

This repository is configured to deploy the frontend from the repo root using [vercel.json](./vercel.json).
The FastAPI backend is deployed separately; for Vercel, use `backend/` as the
project root so Vercel picks up `backend/vercel.json`.

1. Import this repo into Vercel (or run `vercel` from the repo root)
   - Select Node.js 24.x in the project's build settings.
2. Add `VITE_API_BASE_URL` in Vercel Project Settings → Environment Variables
   - Point it at the separately deployed backend API, for example
     `https://<your-backend-project>.vercel.app/api/v1` (or your chosen API host)
   - Also add `VITE_ENTRA_CLIENT_ID`, `VITE_ENTRA_TENANT_ID`, and `VITE_ENTRA_API_SCOPE`
     for Microsoft sign-in (see [docs/authentication.md](./docs/authentication.md))
3. Redeploy after env var updates
4. Ensure the backend `ALLOWED_ORIGINS` includes your Vercel domain(s), and add the
   Vercel URL as a redirect URI on the SPA app registration

Quick validation after deploy:
- `GET <backend-api>/api/v1/health/live` returns 200 (process is running)
- `GET <backend-api>/api/v1/health/ready` returns 200 with required dependencies healthy
- Frontend loads without API/CORS errors in browser console
- Run one small PDF ingestion/review path end-to-end first, then scale up

---

## API Endpoints (v1)

Every endpoint requires a Microsoft Entra ID bearer token with the `Radia.User`
app role unless noted. See [docs/authentication.md](./docs/authentication.md).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health/live` | **Public.** Liveness check - process is running, no external calls |
| GET | `/api/v1/health/ready` | **Public.** Readiness check - cached, bounded-timeout dependency reachability (Azure OpenAI, Azure AI Search, Blob Storage, SharePoint, Jama); returns 503 if a required dependency is down |
| GET | `/api/v1/health` | **Public.** Legacy alias for `/api/v1/health/ready` |
| GET | `/api/v1/auth/me` | Signed-in user, effective roles, and permissions |
| GET | `/api/v1/review/version` | Reviewer bundle version + determinism metadata |
| GET | `/api/v1/standards` | Standards/reference libraries (SharePoint or fallback) |
| POST | `/api/v1/review/requirement` | AI-powered individual requirement review |
| POST | `/api/v1/review/delta` | Score changed requirements against their baseline (no rewrites proposed) |
| GET | `/api/v1/review/history` | The caller's review runs (`Radia.Admin` sees everyone's) |
| POST | `/api/v1/review/history/{id}/disposition` | Apply finding disposition (Accepted/Rejected/Deferred) on your own review |
| POST | `/api/v1/review/history/{id}/decision` | Save a decision on the final recommendation |
| POST | `/api/v1/review/history/{id}/jama-write` | Write the saved, approved Description to the reviewed Jama item |
| GET / PUT / DELETE | `/api/v1/jama/account` | Status / link / unlink the caller's own Jama account |
| GET | `/api/v1/jama/projects`, `/jama/requirements`, `/jama/requirements/{id}` | Jama access as the caller's linked Jama account |
| POST | `/api/v1/search` | Document search (keyword/vector/hybrid) |
| POST | `/api/v1/chat/stream` | Stream grounded RAG answers over server-sent events |
| POST | `/api/v1/ingest` | **`Radia.Admin`.** Trigger document ingestion (blob or SharePoint) |
| POST | `/api/v1/ingest/upload` | **`Radia.Admin`.** Upload and ingest a single document file |
| GET | `/api/v1/ingest/status` | Outcome of the most recent ingestion run (manual or webhook) |
| GET | `/api/v1/ingest/jobs/{job_id}` | **`Radia.Admin`.** Durable status and failure details for one ingestion job |
| POST | `/api/v1/ingest/webhook` | **Public; validated by Graph `clientState`.** Microsoft Graph change-notification receiver (auto-ingestion) |
| POST | `/api/v1/ingest/webhook/subscribe` | **`Radia.Admin`.** Manually (re)create the SharePoint webhook subscription |
| GET | `/api/v1/documents` | List indexed documents |
| GET | `/api/v1/documents/{id}` | Get document metadata and its indexed chunks |
| DELETE | `/api/v1/documents/{id}` | **`Radia.Admin`.** Delete an indexed document (source file untouched) |
| POST | `/api/v1/chat` | RAG question answering |

Interactive docs available at `/api/docs` (non-production environments).

---

## Configuration

All configuration is managed via environment variables, split between
`backend/.env.example` (backend only; set production values directly in your
hosting provider's environment variable settings) and `frontend/.env.example` /
`frontend/.env.production.example` (frontend `VITE_*` variables only) for the
full reference with descriptions.

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI / AI Foundry endpoint (base URL only) |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Chat model deployment (e.g., `gpt-5`) |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Embedding model (e.g., `text-embedding-3-large`) |
| `AZURE_OPENAI_MAX_TOKENS` | Max completion tokens (16384 recommended for GPT-5) |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search endpoint |
| `AZURE_SEARCH_INDEX_NAME` | Search index name (default: `radia-documents`) |
| `AZURE_BLOB_CONNECTION_STRING` | Blob Storage connection string; also used for the ingestion queue |
| `INGESTION_QUEUE_NAME` | Durable ingestion queue name (default: `radia-ingestion`) |
| `INGESTION_MAX_ATTEMPTS` / `INGESTION_MAX_UPLOAD_BYTES` | Fixed five queue deliveries / upload cap (default 4 MiB) |
| `SHAREPOINT_*` | SharePoint Graph API credentials for standards library |
| `SHAREPOINT_WEBHOOK_ENABLED` / `SHAREPOINT_WEBHOOK_PUBLIC_BASE_URL` | Optional auto-ingestion webhook (see Ingestion Pipeline) |
| `ENTRA_*` | Microsoft Entra ID API app registration (required in staging/production; see [docs/authentication.md](./docs/authentication.md)) |
| `VITE_ENTRA_*` | Frontend Microsoft sign-in (SPA app registration, tenant, API scope) |
| `JAMA_BASE_URL` / `JAMA_CREDENTIAL_ENCRYPTION_KEY` | Jama instance and the key that encrypts each user's linked Jama credentials |
| `MCP_ENABLED` / `MCP_SERVER_URL` / `MCP_SERVICE_TOKEN` / `MCP_ALLOWED_TOOLS` | Optional live Jama chat integration; disabled by default and server-side allowlisted |
| `ALLOWED_ORIGINS` / `ALLOWED_ORIGIN_REGEX` | CORS origins; clear the regex when hosting internally |

---

## Security Notes

- Secrets are loaded from `backend/.env` (never committed to git); the frontend's
  `frontend/.env`/`frontend/.env.local` only ever contain public, build-time
  `VITE_*` values
- Microsoft Entra ID SSO with full access-token validation (signature, issuer, audience,
  expiry, tenant, scope) and app-role authorization on every endpoint. Deployed
  environments fail closed without Entra configuration.
- Jama is accessed as each user's own linked Jama account, so Jama enforces their
  project permissions. Linked credentials are encrypted at rest in a dedicated container.
- Jama write-back is only available for a Jama-sourced review after an explicit
  accepted decision; only the Description field is updated, and concurrent Jama
  edits are detected before the write.
- Review history is private to the user who ran it (`Radia.Admin` sees all)
- All API responses use a standardized error envelope (no stack traces exposed)
- Input validation via Pydantic v2 on all endpoints

---

## Running Tests

```bash
cd backend
pytest                          # all tests
pytest -m unit                  # unit tests only
pytest -m integration           # integration tests only (requires Azure)
pytest --cov=app --cov=radia_ai # with coverage report
```

Backend unit-test coverage is enforced at **70%** in CI.

---

## Technology Stack

**Backend:** Python 3.12+, FastAPI, Pydantic v2, Azure OpenAI SDK, Azure AI Search SDK, Azure Blob/Queue SDKs, Azure Functions, PyMuPDF, python-docx, structlog, pytest

**Frontend:** React 18, TypeScript, Vite, MUI v6, React Query v5, Axios, Framer Motion

**AI/ML:** Azure OpenAI (gpt-5 with reasoning capabilities), text-embedding-3-large (3072d), Azure AI Search (vector + semantic + keyword hybrid search)

**Integrations:** Microsoft Entra ID, SharePoint Graph API, Jama Connect, optional MCP chat service

**Infrastructure:** Vercel (frontend and FastAPI API deployment options), Azure Functions (durable ingestion worker), Azure OpenAI, Azure AI Search, Azure Blob Storage, optional Azure Container Apps for mcp-radia

---
## Notes

- **Review history retention.** Review entries and finding dispositions
  are stored durably in Azure Blob Storage and persist across serverless
  invocations, but entries are automatically deleted after 10 days. This requires
  a valid `AZURE_BLOB_CONNECTION_STRING` configuration.

- **Not implemented:** bulk Jama roundtrip, synchronization, and reporting on the
  Jama Roundtrip page; Vitech GENESYS MCP tools.
- **On hold:** per-user Jira/Confluence account linking and using Jira/Confluence
  tools from Radia AI chat. The standalone MCP server has Jira/Confluence tools
  for direct MCP use when configured.
