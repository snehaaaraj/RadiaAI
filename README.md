# Radia AI 2.0

AI-powered Requirements Engineering platform for aerospace and systems teams.
Uses Retrieval-Augmented Generation (RAG) against indexed standards documents to provide 
grounded, traceable, and explainable requirement reviews.

---

## Architecture

For a fuller technical breakdown, see [docs/architecture.md](docs/architecture.md).

```
┌────────────────────────────────────────────────────────────┐
│                         Frontend                           │
│      React + TypeScript + Vite + MUI + Framer Motion      │
│                    port 5173 (Vite dev server)             │
│                                                            │
│  src/pages/                         ← shared app pages     │
│  src/radia_ai/features/resources/   ← resource hub         │
│  src/radia_ai/features/jamaRequirementReviewer/            │
│                                   ← reviewer feature UI    │
│  src/radia_ai/features/jamaRoundtrip/                      │
│                                   ← roundtrip placeholder  │
└──────────────────────┬─────────────────────────────────────┘
                       │  /api/v1/*
┌──────────────────────▼─────────────────────────────────────┐
│                          Backend                           │
│            FastAPI + Python 3.12 + Pydantic v2             │
│                       port 8000                            │
│                                                            │
│  LLM-based review pipeline:                                   │
│    1. RAG retrieval (Azure AI Search) - ~5s                   │
│    2. GPT-5 consolidated review                               │
│    3. Enrich with SharePoint URLs                             │
│    4. Report completion status (or why it failed)             │
│                                                            │
│  On-demand ingestion (POST /api/v1/ingest):                │
│    SharePoint → extract text → chunk → embed → index       │
│    File-hash caching skips unchanged documents             │
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
RadiaAi-2.0/
├── backend/
│   ├── radia_ai/
│   │   ├── main.py                    # project-named FastAPI entrypoint
│   │   └── features/
│   │       ├── jama_requirement_reviewer/
│   │       │   ├── api/v1/endpoints/  # review + standards REST endpoints
│   │       │   ├── connectors/        # SharePoint Graph API client
│   │       │   ├── dependencies/      # DI container + lifespan (Azure client init)
│   │       │   ├── models/            # Pydantic domain models (review, standards)
│   │       │   ├── repositories/      # review history persistence
│   │       │   ├── reviewers/         # review orchestration:
│   │       │   │   ├── base.py        #   abstract reviewer interface
│   │       │   │   ├── orchestrator.py#   LLM review + category scoring + completion
│   │       │   │   └── consolidated.py#   per-category version metadata
│   │       │   │                      #   (analysis lives in the prompt)
│   │       │   ├── schemas/           # API request/response schemas
│   │       │   ├── services/          # review, delta, history, standards services
│   │       │   ├── standards/         # standards registry (fallback)
│   │       │   └── utils/             # normalization, scoring helpers
│   │       └── jama_roundtrip/        # placeholder namespace
│   │
│   ├── app/                           # shared infrastructure layer
│   │   ├── api/v1/endpoints/          # search, ingest, chat, health, documents
│   │   ├── core/
│   │   │   ├── azure_clients.py       # OpenAI, Search, Blob client wrappers
│   │   │   ├── config.py             # Pydantic settings (all Azure config)
│   │   │   ├── logging.py            # structlog configuration
│   │   │   ├── exceptions.py         # domain exception hierarchy
│   │   │   └── security.py           # Entra ID auth middleware
│   │   ├── ingestion/
│   │   │   ├── service.py            # end-to-end ingest pipeline
│   │   │   ├── chunker.py            # token-based text chunking with overlap
│   │   │   └── extractor.py          # PDF/DOCX/TXT text extraction
│   │   ├── rag/
│   │   │   ├── service.py            # RAG retrieval + diversified search
│   │   │   └── llm_review_enhancer_v2.py  # consolidated single-call LLM review
│   │   ├── prompts/
│   │   │   └── review_prompts.py     # GPT-5 system prompt (all categories)
│   │   ├── schemas/                   # shared Pydantic schemas
│   │   ├── dependencies/              # compatibility wrapper (re-exports)
│   │   └── main.py                    # FastAPI app factory + middleware
│   │
│   ├── tests/
│   │   └── unit/                      # 55 unit tests
│   ├── pyproject.toml
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── api/client.ts              # Axios client (5-min timeout for GPT-5)
│   │   ├── components/                # reusable UI components
│   │   ├── hooks/                     # React Query hooks
│   │   ├── pages/                     # shared route-level pages
│   │   ├── context/                   # global app state
│   │   ├── radia_ai/features/
│   │   │   ├── jamaRequirementReviewer/
│   │   │   │   ├── api/              # review API calls
│   │   │   │   ├── components/       # ReviewChangeSet, CategoryScoreGrid, etc.
│   │   │   │   ├── hooks/            # useRequirementReview, useReviewHistory
│   │   │   │   └── pages/            # RequirementReview, DeltaReview, Standards
│   │   │   ├── jamaRoundtrip/
│   │   │   └── resources/
│   │   └── types/                     # TypeScript API interfaces
│   └── package.json
│
├── .env.example
└── README.md
```

---

## Review Pipeline

The review system uses **LLM-based architecture** with GPT-5 + RAG:

```
                        ┌─────────────────────────┐
    Input Requirement   │   LLM Review Pipeline    │
    ─────────────────►  │                         │
                        │  1. Embed query          │
                        │  2. Search (diverse)     │  ← Azure AI Search (~5s)
                        │  3. GPT-5 consolidated   │  ← GPT-5 (~60s)
                        │     review prompt        │
                        │     (language/structure/ │
                        │      verifiability/      │
                        │      certification)      │
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
- All findings include a `suggested_rewrite` (full improved requirement text)
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

Standards documents are ingested from SharePoint on demand via `POST /api/v1/ingest`:

1. **Download** from SharePoint via Microsoft Graph API
2. **Extract text** using PyMuPDF (PDF), python-docx (DOCX), or UTF-8 (TXT/MD)
3. **Chunk** into ~512-word overlapping segments
4. **Embed** via Azure OpenAI text-embedding-3-large (3072 dimensions)
5. **Index** into Azure AI Search with vector + keyword + semantic search
6. **Cache** file hashes - skip re-processing unchanged documents

Single files can also be uploaded directly via `POST /api/v1/ingest/upload`.

### Automatic ingestion via SharePoint webhook (optional)

Instead of (or in addition to) clicking **Ingest Documents** on the Home page,
ingestion can be triggered automatically whenever a file in the SharePoint
standards folder is added, modified, or deleted. This uses a [Microsoft Graph
change-notification subscription](https://learn.microsoft.com/en-us/graph/api/resources/webhooks)
on the folder:

1. Graph POSTs a change notification to `POST /api/v1/ingest/webhook`
2. The `clientState` secret on the notification is verified against the
   subscription record stored in Blob Storage
3. `ingest_from_sharepoint()` runs in the background (file-hash caching still
   applies, so only changed documents are re-indexed)

Because Graph subscriptions expire after a few days, the subscription is
renewed opportunistically on every notification, plus a throttled fallback
check on every `GET /api/v1/standards` call (which the frontend already makes
on page load) in case SharePoint is quiet for an extended period.

Enable it with `SHAREPOINT_WEBHOOK_ENABLED=true` and
`SHAREPOINT_WEBHOOK_PUBLIC_BASE_URL=https://<your-app-domain>` (see
`.env.example`). `POST /api/v1/ingest/webhook/subscribe` can be called to
manually (re)create the subscription, e.g. after first enabling the feature.

**Seeing when ingestion completes:** since webhook-triggered ingestion runs
server-side with no direct connection back to the browser, the Home page
polls `GET /api/v1/ingest/status` every 30 seconds and shows a "Last ingested"
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
- [x] Detailed change-set display:
  - [x] What should change (recommendation)
  - [x] Source-of-truth standard reference with direct SharePoint link
  - [x] Supporting evidence/context for each finding
  - [x] Full suggested rewrite (changeset)

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

### Document ingestion

- [x] On-demand sync from SharePoint via `POST /api/v1/ingest`
- [x] Automatic sync via optional Microsoft Graph webhook when SharePoint documents change
- [x] Manual upload via API endpoint
- [x] File-hash deduplication (skip unchanged)
- [x] PDF, TXT extraction
- [x] Hybrid search (keyword + vector + semantic)

---

## Quick Start

### Prerequisites

- Node.js 20+ (for local frontend development)
- Python 3.12+ (for local backend development)
- Azure subscription with: Azure OpenAI (GPT-5 + text-embedding-3-large), Azure AI Search, Azure Blob Storage

### 1. Clone and configure

```bash
git clone <repo-url>
cd RadiaAi-2.0
cp .env.example .env
# Edit .env with your Azure credentials
```

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

```bash
cd frontend
npm install
npm run start
      # starts Vite dev server on :5173, proxies /api to :8000
```

### 4. Frontend deployment to Vercel (temporary production path)

This repository is configured to deploy the frontend from the repo root using [vercel.json](./vercel.json).

1. Import this repo into Vercel (or run `vercel` from the repo root)
2. Add `VITE_API_BASE_URL` in Vercel Project Settings → Environment Variables
   - Value format: `https://<your-azure-backend>.azurewebsites.net/api/v1`
3. Redeploy after env var updates
4. Ensure the backend `ALLOWED_ORIGINS` includes your Vercel domain(s)

Quick validation after deploy:
- `GET <azure-backend>/api/v1/health` returns 200
- Frontend loads without API/CORS errors in browser console
- Run one small PDF ingestion/review path end-to-end first, then scale up

---

## API Endpoints (v1)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Application health check |
| GET | `/api/v1/review/version` | Reviewer bundle version + determinism metadata |
| GET | `/api/v1/standards` | Standards/reference libraries (SharePoint or fallback) |
| POST | `/api/v1/review/requirement` | AI-powered individual requirement review |
| POST | `/api/v1/review/delta` | Score changed requirements against their baseline (no rewrites proposed) |
| GET | `/api/v1/review/history` | List stored review runs and findings |
| POST | `/api/v1/review/history/{id}/disposition` | Apply finding disposition (Accepted/Rejected/Deferred) |
| POST | `/api/v1/search` | Document search (keyword/vector/hybrid) |
| POST | `/api/v1/ingest` | Trigger document ingestion (blob or SharePoint) |
| POST | `/api/v1/ingest/upload` | Upload and ingest a single document file |
| GET | `/api/v1/ingest/status` | Outcome of the most recent ingestion run (manual or webhook) |
| POST | `/api/v1/ingest/webhook` | Microsoft Graph change-notification receiver (auto-ingestion) |
| POST | `/api/v1/ingest/webhook/subscribe` | Manually (re)create the SharePoint webhook subscription |
| GET | `/api/v1/documents` | List indexed documents |
| POST | `/api/v1/chat` | RAG question answering |

Interactive docs available at `/api/docs` (non-production environments).

---

## Configuration

All configuration is managed via environment variables. See `.env.example` for
the full reference with descriptions.

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI / AI Foundry endpoint (base URL only) |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Chat model deployment (e.g., `gpt-5`) |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Embedding model (e.g., `text-embedding-3-large`) |
| `AZURE_OPENAI_MAX_TOKENS` | Max completion tokens (16384 recommended for GPT-5) |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search endpoint |
| `AZURE_SEARCH_INDEX_NAME` | Search index name (default: `radia-documents`) |
| `AZURE_BLOB_CONNECTION_STRING` | Blob Storage connection string |
| `SHAREPOINT_*` | SharePoint Graph API credentials for standards library |
| `SHAREPOINT_WEBHOOK_ENABLED` / `SHAREPOINT_WEBHOOK_PUBLIC_BASE_URL` | Optional auto-ingestion webhook (see Ingestion Pipeline) |
| `ENTRA_*` | Microsoft Entra ID settings (leave empty for local dev) |

---

## Security Notes

- Secrets are loaded from `.env` (never committed to git)
- Authentication supports Microsoft Entra ID configuration with local development fallback
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

Backend unit-test coverage is enforced at **70%** in CI. Coverage increases are
staged with focused tests for authentication and authorization, configuration
validation, chat/RAG, ingestion and webhook failures, blob persistence, search
failures, and API contracts.

---

## Technology Stack

**Backend:** Python 3.12, FastAPI, Pydantic v2, Azure OpenAI SDK, Azure AI Search SDK, Azure Blob SDK, PyMuPDF, python-docx, structlog, pytest

**Frontend:** React 18, TypeScript, Vite, MUI v6, React Query v5, Axios, Framer Motion

**AI/ML:** Azure OpenAI (gpt-5 with reasoning capabilities), text-embedding-3-large (3072d), Azure AI Search (vector + semantic + keyword hybrid search)

**Infrastructure:** Azure App Service / Container Apps, Azure OpenAI, Azure AI Search, Azure Blob Storage

---
## Notes

- **Review history retention.** Review entries and finding dispositions
  are stored durably in Azure Blob Storage and persist across serverless
  invocations, but entries are automatically deleted after 10 days. This requires
  a valid `AZURE_BLOB_CONNECTION_STRING` configuration.

- Partial features have functional UIs and basic backend integration but may require enhancement for production workflows.
