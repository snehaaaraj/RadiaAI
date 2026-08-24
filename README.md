# Radia AI

AI-powered Requirements Engineering platform for aerospace teams.
Uses Azure OpenAI (GPT-5) with Retrieval-Augmented Generation (RAG) against
indexed standards documents to provide grounded, traceable requirement reviews.

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
│  Hybrid review pipeline:                                   │
│    1. Deterministic rules (regex, word lists) — instant    │
│    2. RAG retrieval (Azure AI Search) — ~5s               │
│    3. GPT-5 consolidated review — runs in parallel         │
│    4. Merge + enrich with SharePoint URLs                  │
│                                                            │
│  Auto-ingestion at startup:                                │
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
│   │       │   ├── reviewers/         # hybrid reviewer modules:
│   │       │   │   ├── base.py        #   abstract reviewer interface
│   │       │   │   ├── orchestrator.py#   parallel deterministic + LLM orchestration
│   │       │   │   ├── language/      #   modal verbs, ambiguity, banned words
│   │       │   │   ├── structure/     #   compound reqs, EARS syntax, levels
│   │       │   │   ├── verifiability/ #   measurability, operating conditions
│   │       │   │   ├── traceability/  #   parent/child, allocation (LLM-powered)
│   │       │   │   └── certification/ #   DO-178, DAL, safety (LLM-powered)
│   │       │   ├── rules/             # deterministic rule constants (word lists)
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
│   │   └── unit/                      # 19 unit tests
│   ├── startup.sh                     # Azure App Service gunicorn startup
│   ├── pyproject.toml
│   ├── requirements.txt               # production dependencies
│   └── requirements-dev.txt           # dev/test dependencies
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
├── docker/
│   └── nginx.conf
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## Review Pipeline

The review system uses a **hybrid architecture** — deterministic rules run in parallel
with a single consolidated GPT-5 + RAG call:

```
                        ┌─────────────────────────┐
    Input Requirement   │    ThreadPoolExecutor    │
    ─────────────────►  │                         │
                        │  Thread 1: Deterministic │  ← regex rules (~1ms)
                        │    language/structure/   │
                        │    verifiability checks  │
                        │                         │
                        │  Thread 2: LLM + RAG    │  ← GPT-5 (~60s)
                        │    1. Embed query        │
                        │    2. Search (diverse)   │
                        │    3. GPT-5 consolidated │
                        │       review prompt      │
                        └────────────┬────────────┘
                                     │
                              Merge findings
                              Enrich references
                              (SharePoint URLs)
                                     │
                                     ▼
                          Review Response (JSON)
```

**Key behaviors:**
- Deterministic rules provide instant feedback for common issues
- GPT-5 provides deeper analysis grounded in indexed standards documents
- All findings include a `suggested_rewrite` (full improved requirement text)
- References point to actual SharePoint document URLs, not hardcoded names
- File-hash caching: unchanged documents are not re-embedded on restart

---

## Ingestion Pipeline

Standards documents are automatically ingested from SharePoint at server startup:

1. **Download** from SharePoint via Microsoft Graph API
2. **Extract text** using PyMuPDF (PDF), python-docx (DOCX), or UTF-8 (TXT/MD)
3. **Chunk** into ~512-word overlapping segments
4. **Embed** via Azure OpenAI text-embedding-3-large (3072 dimensions)
5. **Index** into Azure AI Search with vector + keyword + semantic search
6. **Cache** file hashes — skip re-processing unchanged documents

Manual ingestion is also available via `POST /api/v1/ingest` or file upload.

---

## Functional Coverage

### Requirements review workflow

- [x] Upload or copy/paste requirement content
- [x] AI-powered review across 5 categories (language, structure, verifiability, traceability, certification)
- [x] Color-coded overall scoring
- [x] Sub-category scoring displayed directly below overall score
- [x] Persistent review state across navigation with explicit **Clear Review**
- [x] Findings grounded in indexed standards with source document links

### AI-assisted modification workflow

- [x] AI-generated suggested changes from findings
- [x] Detailed change-set display:
  - [x] What should change (recommendation)
  - [x] Source-of-truth standard reference with direct SharePoint link
  - [x] Supporting evidence/context for each finding
  - [x] Full suggested rewrite (changeset)

### Document ingestion

- [x] Auto-sync from SharePoint at startup
- [x] Manual upload via API endpoint
- [x] File-hash deduplication (skip unchanged)
- [x] PDF, TXT extraction
- [x] Hybrid search (keyword + vector + semantic)

---

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.12+
- Azure subscription with: Azure OpenAI (GPT-5 + text-embedding-3-large), Azure AI Search, Azure Blob Storage

### 1. Clone and configure

```bash
git clone <repo-url>
cd RadiaAi-2.0
cp .env.example .env
# Edit .env with your Azure credentials
```

### 2. Start the backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn radia_ai.main:app --reload --port 8000
```

On first start, the server will:
1. Create/update the Azure AI Search index
2. Download standards from SharePoint
3. Extract, chunk, embed, and index all documents
4. Subsequent starts skip unchanged documents (~10s startup)

Backend API available at: http://localhost:8000/api/docs

### 3. Start the frontend (in a new terminal)

```bash
cd frontend
npm install
npm run start
# Vite dev server on http://localhost:5173
# Proxies /api/* calls to http://localhost:8000
```

Frontend available at: http://localhost:5173

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
- Containers run as non-root users
- Input validation via Pydantic v2 on all endpoints

---

## Running Tests

```bash
cd backend
pytest                          # all tests (19 unit tests)
pytest -m unit                  # unit tests only
pytest -m integration           # integration tests only (requires Azure)
pytest --cov=app --cov=radia_ai # with coverage report
```

---

## Technology Stack

**Backend:** Python 3.12, FastAPI, Pydantic v2, Azure OpenAI SDK, Azure AI Search SDK, Azure Blob SDK, PyMuPDF, python-docx, structlog, pytest

**Frontend:** React 18, TypeScript, Vite, MUI v6, React Query v5, Axios, Framer Motion

**AI/ML:** Azure OpenAI GPT-5 (reasoning), text-embedding-3-large (3072d), Azure AI Search (vector + semantic)

**Infrastructure:** Azure App Service (Free F1, Python), Vercel (Frontend)
