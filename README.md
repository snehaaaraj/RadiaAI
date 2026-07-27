# Radia AI

Enterprise Retrieval-Augmented Generation (RAG) platform for engineering knowledge.
Initially designed to review Jama Systems requirements; architected to evolve into a
full enterprise engineering knowledge assistant.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                       Frontend                          │
│          React + TypeScript + Vite + MUI                │
│                  port 3000 (nginx)                      │
└─────────────────────┬───────────────────────────────────┘
                      │  /api/v1/*
┌─────────────────────▼───────────────────────────────────┐
│                      Backend                            │
│          FastAPI + Python 3.12 + Pydantic v2            │
│                     port 8000                           │
│                                                         │
│  api/v1/       ← routes + request validation only       │
│  services/     ← business logic (Phase 2+)              │
│  rag/          ← RAG pipeline stages (Phase 4)          │
│  ingestion/    ← document ingestion (Phase 2)           │
│  connectors/   ← source adapters (Phase 2+)             │
└──────────┬──────────┬────────────────┬──────────────────┘
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
│   ├── app/
│   │   ├── api/v1/endpoints/   # HTTP endpoint handlers (thin — no logic)
│   │   ├── core/               # config, logging, exceptions, security
│   │   ├── schemas/            # Pydantic v2 request/response models
│   │   ├── services/           # business logic (Phase 2+)
│   │   ├── rag/                # RAG pipeline (Phase 4)
│   │   ├── ingestion/          # ingestion pipeline (Phase 2)
│   │   ├── connectors/         # document source connectors (Phase 2+)
│   │   ├── dependencies/       # FastAPI DI container
│   │   └── main.py             # app factory
│   ├── tests/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── api/        # typed Axios functions
│   │   ├── components/ # reusable UI components
│   │   ├── hooks/      # React Query hooks
│   │   ├── pages/      # route-level page components
│   │   ├── context/    # global app state
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

## Phase Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Repo structure, Docker, config, FastAPI skeleton, React skeleton | **Complete** |
| 2 | Azure wrappers, ingestion pipeline, chunking, embeddings | Planned |
| 3 | Azure AI Search indexing + search service | Planned |
| 4 | RAG pipeline (retrieval → prompt → LLM) | Planned |
| 5 | React chat interface (full UI) | Planned |
| 6 | Testing, logging, monitoring | Planned |

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

### 3. Local backend development (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 4. Local frontend development (without Docker)

```bash
cd frontend
npm install
npm run dev     # starts Vite dev server on :5173, proxies /api to :8000
```

---

## Running Tests

```bash
cd backend
pytest                          # all tests
pytest -m unit                  # unit tests only
pytest -m integration           # integration tests only (requires Azure)
pytest --cov=app                # with coverage report
```

---

## API Endpoints (v1)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Application health check |
| POST | `/api/v1/chat` | RAG question answering |
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
- Authentication uses Microsoft Entra ID (stubbed in Phase 1, active in Phase 2)
- All API responses use a standardized error envelope (no stack traces exposed)
- Containers run as non-root users
- Input validation via Pydantic v2 on all endpoints

---

## Technology Stack

**Backend:** Python 3.12, FastAPI, Pydantic v2, Azure SDK, structlog, pytest

**Frontend:** React 18, TypeScript, Vite, MUI v6, React Query v5, Axios

**Infrastructure:** Docker, nginx, Azure App Service / Container Apps
