# Radia AI

Deterministic AI-assisted Requirements Engineering platform for aerospace teams.
Originally started as a Jama requirements reviewer and now refactored toward
structured, explainable requirement quality workflows.

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
│  radia_ai/main.py                  ← primary entrypoint    │
│  radia_ai/features/jama_requirement_reviewer/              │
│                                   ← active reviewer logic  │
│  radia_ai/features/jama_roundtrip/                         │
│                                   ← future feature slot    │
│  app/                              ← shared + compat layer │
└──────────┬──────────┬────────────────┬─────────────────────┘
           │          │                │
    ┌──────▼──┐ ┌─────▼──────┐ ┌──────▼──────┐
    │  Azure  │ │  Azure AI  │ │   Azure     │
    │ OpenAI  │ │   Search   │ │   Blob      │
    └─────────┘ └────────────┘ └─────────────┘
```

---

## Project Structure

```
RadiaAi-2.0/
├── backend/
│   ├── radia_ai/
│   │   ├── main.py             # project-named FastAPI entrypoint
│   │   └── features/
│   │       ├── jama_requirement_reviewer/  # active reviewer implementation
│   │       └── jama_roundtrip/             # placeholder namespace
│   ├── app/                   # shared legacy package + compatibility wrappers
│   │   ├── api/v1/endpoints/  # shared/non-review endpoints + wrapper modules
│   │   ├── core/              # config, logging, exceptions, security
│   │   ├── schemas/           # Pydantic v2 request/response models
│   │   ├── services/          # shared or compatibility service exports
│   │   ├── rag/               # retrieval-augmented generation components
│   │   ├── ingestion/         # document ingestion pipeline
│   │   ├── connectors/        # source system adapters
│   │   ├── dependencies/      # shared DI + reviewer compatibility wrappers
│   │   └── main.py            # compatibility entrypoint
│   ├── tests/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── assets/     # logos and static UI assets
│   │   ├── components/ # reusable UI components
│   │   ├── hooks/      # React Query hooks
│   │   ├── pages/      # shared route-level page components
│   │   ├── context/    # global app state
│   │   ├── radia_ai/
│   │   │   └── features/
│   │   │       ├── jamaRequirementReviewer/
│   │   │       │   ├── api/
│   │   │       │   ├── components/
│   │   │       │   ├── hooks/
│   │   │       │   └── pages/
│   │   │       ├── jamaRoundtrip/
│   │   │       │   └── pages/
│   │   │       └── resources/
│   │   │           └── pages/
│   │   └── types/      # TypeScript API interfaces
│   ├── Dockerfile
│   └── package.json
│
├── docker/
│   └── nginx.conf
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## Functional Coverage Status

### Requirements analysis workflow

- [x] Upload or copy/paste requirement content
- [x] Color-coded overall scoring
- [x] Sub-category scoring displayed directly below overall score
- [x] Persistent review state across navigation with explicit **Clear Review**

### AI-assisted modification workflow

- [x] AI-generated suggested changes from findings
- [x] Detailed change-set display:
  - [x] What was changed
  - [x] Source-of-truth standard reference with direct link
  - [x] Supporting evidence/context for each change

---

## Current Frontend Experience

- Dedicated **Launchpad** landing page at `/`
- Dedicated **Radia AI Resources** page at `/radia-ai`
- Main app workspace now starts at `/workspace`
- Dedicated **Jama Roundtrip** placeholder page at `/jama-roundtrip`
- Theme-aware branding with separate light and dark logo assets
- Landing/resources header navigation:
  - `RADIA | RADIA AI | Jama Requirement Reviewer | Jama Roundtrip`
- Workspace header breadcrumb:
  - `RADIA | Radia AI | <current resource> | <current sub-page>`
- Resource-based workspace launch:
  - selecting **Open workspace** launches the resource at `/workspace` (resource home)
- Personalization controls for:
  - theme mode (system / light / dark)
  - default workspace start page
  - sidebar open/collapsed state
  - review-complete sound notification
- Animated page transitions and cards using **Framer Motion**
- Persistent review form/results state across navigation for:
  - individual requirement review
  - delta review
- Explicit **Clear Review** actions to reset persisted review state
- Auto-scroll to score/result area after a review completes
- Improved review result presentation with:
  - overall score hero
  - per-category scoring cards
  - severity color-coding
  - clearer suggested changes, evidence, and standards references

---

## Quick Start

### Prerequisites

- Docker Desktop
- Node.js 20+ (for local frontend development)
- Python 3.12+ (for local backend development)
- Azure subscription with: Azure OpenAI, Azure AI Search, Azure Blob Storage

### 1. Clone and configure

```bash
git clone <repo-url>
cd RadiaAi-2.0
cp .env.example .env
# Edit .env with your Azure credentials
```

### 2. Run with Docker Compose

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/api/docs

The Dockerized frontend serves:

- Launchpad: `/`
- Radia AI Resources: `/radia-ai`
- Jama Roundtrip placeholder: `/jama-roundtrip`
- Main workspace: `/workspace`

### 3. Local backend development (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn radia_ai.main:app --reload --port 8000
```

### 4. Local frontend development (without Docker)

```bash
cd frontend
npm install
npm run start
      # starts Vite dev server on :5173, proxies /api to :8000
```

Local frontend URLs:

- Launchpad: http://localhost:5173/
- Radia AI Resources: http://localhost:5173/radia-ai
- Jama Roundtrip placeholder: http://localhost:5173/jama-roundtrip
- Workspace: http://localhost:5173/workspace

---

## Frontend Styling Convention

- Prefer MUI theme overrides and sidecar `*.styles.ts` files over large inline `sx` objects in page/component JSX.
- Keep styling next to the component it belongs to (for example, `Settings.tsx` + `Settings.styles.ts`) instead of introducing global CSS.
- Use raw `.css` or CSS modules only when a component is mostly static and does not need MUI theme tokens, responsive objects, or component-state styling.

---

## Running Tests

```bash
cd backend
pytest                          # all tests
pytest -m unit                  # unit tests only
pytest -m integration           # integration tests only (requires Azure)
pytest --cov=app --cov=radia_ai # with coverage report during migration
```

---

## API Endpoints (v1)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Application health check |
| GET | `/api/v1/review/version` | Reviewer/prompt/standards determinism metadata |
| GET | `/api/v1/standards` | Standards/reference libraries used by reviewers |
| POST | `/api/v1/review/requirement` | Deterministic individual requirement review |
| POST | `/api/v1/review/delta` | Deterministic incremental delta review |
| GET | `/api/v1/review/history` | List stored review runs and findings |
| POST | `/api/v1/review/history/{review_id}/disposition` | Apply finding disposition (Accepted/Rejected/Deferred) |
| POST | `/api/v1/chat` | Legacy RAG question answering (migration in progress) |
| POST | `/api/v1/search` | Document search (keyword/vector/hybrid) |
| POST | `/api/v1/ingest` | Trigger document ingestion |
| GET | `/api/v1/documents` | List indexed documents |

Interactive docs available at `/api/docs` (non-production environments).

---

## Configuration

All configuration is managed via environment variables. See `.env.example` for
the full reference with descriptions for every variable.

Key settings:

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource URL |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Deployed model name (e.g., `gpt-4o`) |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Embedding model deployment name |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search endpoint |
| `AZURE_SEARCH_INDEX_NAME` | Search index name |
| `AZURE_BLOB_CONNECTION_STRING` | Blob Storage connection string |
| `ENTRA_*` | Microsoft Entra ID settings (leave empty for local dev) |

---

## Security Notes

- Secrets are loaded from `.env` (never committed to git)
- Authentication supports Microsoft Entra ID configuration with local development fallback
- All API responses use a standardized error envelope (no stack traces exposed)
- Containers run as non-root users
- Input validation via Pydantic v2 on all endpoints

---

## Technology Stack

**Backend:** Python 3.12, FastAPI, Pydantic v2, Azure SDK, structlog, pytest

**Frontend:** React 18, TypeScript, Vite, MUI v6, React Query v5, Axios, Framer Motion

**Infrastructure:** Docker, nginx, Azure App Service / Container Apps
