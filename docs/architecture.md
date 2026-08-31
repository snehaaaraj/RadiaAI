# Radia AI Architecture

Radia AI is an explainable requirements-engineering platform for aerospace and systems teams. It combines a React frontend with a FastAPI backend to support requirement quality review, delta review, standards lookup, review history, and document-oriented workflows.

## 1. System goals

- Make requirement review repeatable and explainable
- Keep every finding grounded in standards
- Preserve review history and disposition decisions
- Provide clear references back to engineering standards
- Support a modern, usable workflow for technical reviewers

## 2. High-level system view

```text
┌──────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│     React + TypeScript + Vite + MUI + React Query           │
│   Landing / Workspace / Review / Standards / History        │
└───────────────────────┬──────────────────────────────────────┘
                        │ /api/v1/*
┌───────────────────────▼──────────────────────────────────────┐
│                         Backend                              │
│                   FastAPI + Python 3.12                     │
│  api/      → HTTP route handlers                             │
│  services/  → orchestration and business rules               │
│  reviewers/ → LLM-based review engines                      │
│  standards/ → standards catalog and reference resolution    │
│  diff/     → delta computation for revision review          │
│  repositories/ → review history persistence and dispositions│
└───────────────┬───────────────────────┬──────────────────────┘
                │                       │
        ┌───────▼───────┐       ┌──────▼─────────┐
        │ Azure OpenAI   │       │ SharePoint     │
        │ Azure Search   │       │ Standards lib  │
        │ Azure Blob     │       │ fallback registry│
        └─────────────────┘       └────────────────┘
```

## 3. Frontend architecture

The frontend is a single-page application built with React and TypeScript.

### Core stack

- **React 18**
- **TypeScript**
- **Vite**
- **Material UI**
- **React Query**
- **Framer Motion**

### Primary routes

- `/` — Launchpad
- `/radia-ai` — Radia AI Resources
- `/workspace` — Main application workspace
- `/review/requirement` — Single requirement review
- `/review/delta` — Delta review
- `/review/history` — Review history
- `/standards` — Standards catalog
- `/chat` — Document Q&A
- `/search` — Search
- `/documents` — Documents
- `/settings` — Personalization controls

### Frontend behavior

- Persistent UI preferences in local storage
- Theme, accent color, density, motion, sidebar state, and default workspace routing
- Animated page transitions and cards
- Review state preserved across navigation
- Clear review actions to reset stored review state
- Result presentation focused on score, category breakdown, findings, evidence, and rewrite guidance

## 4. Backend architecture

The backend is a layered FastAPI application.

### Application bootstrap

`backend/app/main.py` creates the FastAPI app and configures:

- CORS middleware
- request ID generation and propagation
- structured logging
- global exception handlers
- API router mounting

### Layered structure

- **api/v1/endpoints**: thin request/response handlers
- **services**: business logic and workflow orchestration
- **reviewers**: deterministic quality engines
- **models / schemas**: validated API contracts
- **standards**: standards registry and catalog lookup
- **diff**: revision comparison logic
- **repositories**: history persistence abstraction
- **connectors**: external source adapters

## 5. Review workflow

The review engine provides explainable, LLM-based requirement analysis.

### Single requirement review

1. The user submits one requirement.
2. The orchestrator runs the enabled reviewer modules.
3. Each reviewer returns findings and a category status.
4. Findings are enriched with standards references when possible.
5. The response includes:
   - overall status
   - category results
   - findings
   - version metadata
   - review ID

### Delta review

1. The system compares baseline and updated requirement sets.
2. It identifies:
   - new requirements
   - modified requirements
   - deleted requirements
   - changed trace links
3. Only changed requirements are re-reviewed.
4. Results are aggregated into a delta response with a change summary.

## 6. Reviewer modules

Radia AI currently uses modular reviewer engines:

- **Language reviewer**: mandatory wording, ambiguous phrasing, banned terms, passive voice
- **Structure reviewer**: one requirement per statement, subjective wording, hierarchy level
- **Verifiability reviewer**: measurable criteria and operating conditions
- **Traceability reviewer**: registered in the orchestrator, currently a skeleton
- **Certification reviewer**: registered in the orchestrator, currently a skeleton

Each reviewer is versioned so results can be traced back to:

- reviewer implementation version
- prompt version
- standards version
- runtime configuration snapshot

## 7. Standards and reference resolution

The standards service resolves reviewer references against a standards catalog.

Priority order:

1. **SharePoint** standards library, when configured
2. **Registry fallback** when SharePoint is unavailable

This allows findings to link back to a source document or guidance entry and keeps the review explainable.

## 8. Review history

Completed reviews are stored in an in-memory history repository for now.

Stored data includes:

- review ID
- workflow type
- subject ID
- timestamp
- overall result
- findings
- category results
- determinism snapshot
- disposition records

Users can apply dispositions to findings:

- Accepted
- Rejected
- Deferred

## 9. Document and RAG surfaces

Radia AI also includes the foundation for document-centric workflows:

- chat over indexed content
- document search
- document ingestion
- document listing

These endpoints are present as API contracts and partial stubs in the current codebase, supporting later expansion into a full retrieval-augmented knowledge workflow.

## 10. Configuration and deployment

Runtime configuration is controlled through environment variables.

Key services:

- Azure OpenAI
- Azure AI Search
- Azure Blob Storage
- Microsoft Entra ID
- SharePoint

The project supports:

- Docker Compose for local full-stack startup
- local backend development with Uvicorn
- local frontend development with Vite

## 11. Security and operational notes

- Secrets are loaded from `.env`
- API responses use a consistent error envelope
- Request IDs are propagated across logs and responses
- Input validation is handled with Pydantic
- Production avoids exposing stack traces

## 12. Current implementation status

Implemented and central to the product:

- deterministic requirement review
- delta review
- standards catalog browsing
- review history
- workspace and launchpad UX

Partially implemented or scaffolded:

- document search
- ingestion
- chat/RAG pipeline
- traceability reviewer
- certification reviewer

## 13. Summary

Radia AI is an enterprise requirements-quality platform that emphasizes deterministic behavior, structured findings, and audit-friendly review workflows. Its architecture cleanly separates UI, orchestration, reviewer logic, and standards resolution so the system can evolve without losing explainability or reproducibility.
