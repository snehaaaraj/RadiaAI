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
│                    port 3000 (nginx)                       │
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
│    1. RAG retrieval (Azure AI Search) — ~5s                   │
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
│   │       │   │   ├── orchestrator.py#   LLM review + completion status
│   │       │   │   ├── traceability/  #   version metadata (analysis lives in prompt)
│   │       │   │   └── certification/ #   version metadata (analysis lives in prompt)
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
                        │      traceability/       │
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
- GPT-5 provides deeper analysis grounded in indexed standards documents
- All findings include a `suggested_rewrite` (full improved requirement text)
- References point to actual SharePoint document URLs, not hardcoded names
- File-hash caching: unchanged documents are not re-embedded on restart
- Every response carries a **completion record** — a review that could not run
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
6. **Cache** file hashes — skip re-processing unchanged documents

Single files can also be uploaded directly via `POST /api/v1/ingest/upload`.

---

## Functional Coverage

### Requirements review workflow

- [x] Upload or copy/paste requirement content
- [x] AI-powered review across 5 categories (language, structure, verifiability, traceability, certification)
- [x] Color-coded overall scoring
- [x] Sub-category scoring displayed directly below overall score
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

### Document ingestion

- [x] On-demand sync from SharePoint via `POST /api/v1/ingest`
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
pip install -r requirements.txt
uvicorn radia_ai.main:app --reload --port 8000
```

On start, the server creates/updates the Azure AI Search index.

Standards are **not** ingested at startup — that keeps cold starts viable on
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
| POST | `/api/v1/review/delta` | Incremental delta review for changed requirements |
| GET | `/api/v1/review/history` | List stored review runs and findings |
| POST | `/api/v1/review/history/{id}/disposition` | Apply finding disposition (Accepted/Rejected/Deferred) |
| POST | `/api/v1/search` | Document search (keyword/vector/hybrid) |
| POST | `/api/v1/ingest` | Trigger document ingestion (blob or SharePoint) |
| POST | `/api/v1/ingest/upload` | Upload and ingest a single document file |
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
pytest                          # all tests (55 unit tests)
pytest -m unit                  # unit tests only
pytest -m integration           # integration tests only (requires Azure)
pytest --cov=app --cov=radia_ai # with coverage report
```

---

## Technology Stack

**Backend:** Python 3.12, FastAPI, Pydantic v2, Azure OpenAI SDK, Azure AI Search SDK, Azure Blob SDK, PyMuPDF, python-docx, structlog, pytest

**Frontend:** React 18, TypeScript, Vite, MUI v6, React Query v5, Axios, Framer Motion

**AI/ML:** Azure OpenAI (GPT-5 with reasoning capabilities), text-embedding-3-large (3072d), Azure AI Search (vector + semantic + keyword hybrid search)

**Infrastructure:** Azure App Service / Container Apps, Azure OpenAI, Azure AI Search, Azure Blob Storage

---

## Known Limitations

- **Review history is not durable.** It lives in an in-memory repository, so on
  serverless hosting each invocation starts empty and disposition writes will not
  find their review. Durable storage is needed before history is production-ready.
- **Delta dispositions target the wrong finding.** Delta history flattens findings
  across all reviewed requirements, while the UI sends a per-requirement index.
- **A cleanly passing category shows as "Not evaluated"** — category results are
  only emitted for categories that produced a finding.
- **The category grid hides traceability**, although the review pipeline produces
  traceability findings.

**Note:** Partial features have functional UIs and basic backend integration but may require enhancement for production workflows.
