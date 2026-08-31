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
- **reviewers**: LLM review orchestration and reviewer version metadata
- **rag**: retrieval and the consolidated LLM review call
- **prompts**: the consolidated review system prompt
- **models / schemas**: validated API contracts
- **standards**: standards registry and catalog lookup
- **diff**: revision comparison logic
- **repositories**: history persistence abstraction
- **connectors**: external source adapters

## 5. Review workflow

The review engine provides explainable, standards-grounded requirement analysis.

### Single requirement review

1. The user submits one requirement.
2. The orchestrator normalizes the input (fielded Jama text is flattened to
   Title / Description / Rationale).
3. `LLMReviewEnhancer` retrieves standards context from Azure AI Search, using
   source-diversified retrieval so several documents can be cited.
4. One consolidated GPT-5 call produces findings across all five categories.
5. Findings are enriched with standards references and SharePoint URLs.
6. Category statuses are derived from the findings and aggregated into an overall
   status.
7. The response includes:
   - overall status
   - completion record (see §6)
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
4. Results are aggregated into a delta response with a change summary and a
   run-level completion record.

## 6. Review completion contract

The review *verdict* and the review *process outcome* are separate fields, because
an empty findings list is ambiguous on its own — it means either "this requirement
is clean" or "the engine never ran".

Every review response carries a `completion` record:

| Field | Meaning |
|-------|---------|
| `status` | `complete`, `partial` (batch: some items evaluated), or `failed` |
| `reason` | machine-readable cause, null when complete |
| `message` | reviewer-facing explanation |

Failure reasons are raised by the specific stage that broke:

- `review_engine_unavailable` — no LLM enhancer could be constructed
- `no_standards_context` — retrieval returned nothing to review against
- `retrieval_failed` — Azure AI Search errored
- `llm_call_failed` — the GPT-5 call errored
- `invalid_llm_response` — the response was not parsable JSON of the expected shape

When a review does not complete, `overall` is `Not Evaluated` and findings and
category results are empty. The frontend renders the failure notice in place of
the score, so an unevaluated requirement is never displayed as a passing one.

## 7. Reviewer modules

All requirement analysis happens in a single consolidated GPT-5 call
(`app/prompts/review_prompts.py`), covering five categories:

- **Language**: mandatory modal usage, banned words, ambiguous wording, passive voice
- **Structure**: one requirement per statement, human-judgment language, EARS syntax, requirement level
- **Verifiability**: quantitative limits, operating conditions, verification method
- **Traceability**: parent traceability, allocation, derived requirements, bidirectional tracing
- **Certification**: DO-178C / DO-254 / ARP4754A alignment, verification methods, safety language, DAL

The reviewer modules registered with the orchestrator
(`reviewers/traceability/`, `reviewers/certification/`) no longer carry rule logic.
They exist to publish version metadata, so a result can be traced back to:

- reviewer implementation version
- prompt version
- standards version
- runtime configuration snapshot

Note that "determinism" metadata records the reproducibility *conditions* of a run.
Because analysis is LLM-based, identical input is not guaranteed to produce
byte-identical output.

## 8. Standards and reference resolution

The standards service resolves reviewer references against a standards catalog.

Priority order:

1. **SharePoint** standards library, when configured
2. **Registry fallback** when SharePoint is unavailable

This allows findings to link back to a source document or guidance entry and keeps the review explainable.

## 9. Review history

Completed reviews are stored in an in-memory history repository for now.

Stored data includes:

- review ID
- workflow type
- subject ID
- timestamp
- overall result
- completion record
- findings
- category results
- determinism snapshot
- disposition records

Users can apply dispositions to findings:

- Accepted
- Rejected
- Deferred

**Known limitation:** the repository is process-local. On a serverless deployment
each invocation starts a fresh process, so history will read as empty and
disposition writes will not find their review. Durable storage is required before
history can be relied on in production.

## 10. Document and RAG surfaces

Radia AI also includes document-centric workflows:

- chat over indexed content
- document search (keyword / vector / hybrid)
- document ingestion (SharePoint or uploaded file)
- document listing

Ingestion extracts text, chunks it, embeds it with `text-embedding-3-large`, and
indexes it into Azure AI Search. File hashes are recorded so unchanged documents
are not re-embedded.

Ingestion runs on demand via `POST /api/v1/ingest` — it is deliberately not run at
startup, which keeps cold starts viable on serverless hosting. The review pipeline
depends on this index being populated: with an empty index, reviews return
`no_standards_context` rather than findings.

## 11. Configuration and deployment

Runtime configuration is controlled through environment variables.

Key services:

- Azure OpenAI
- Azure AI Search
- Azure Blob Storage
- Microsoft Entra ID
- SharePoint

The project supports:

- local backend development with Uvicorn
- local frontend development with Vite
- frontend deployment to Vercel from the repo root (`vercel.json`)

## 12. Security and operational notes

- Secrets are loaded from `.env`
- API responses use a consistent error envelope
- Request IDs are propagated across logs and responses
- Input validation is handled with Pydantic
- Production avoids exposing stack traces
- A review that cannot run reports its failure cause instead of returning an
  empty result that would read as a pass

## 13. Current implementation status

Implemented and central to the product:

- LLM-based requirement review grounded in indexed standards
- explicit review completion reporting (§6)
- delta review over changed requirements
- standards catalog browsing
- document ingestion, search, and chat over the index
- workspace and launchpad UX

Known gaps:

- **review history is not durable** — in-memory only (§9)
- **delta dispositions target the wrong finding** — delta history flattens findings
  across requirements while the UI sends a per-requirement index
- category scoring only reports categories that produced a finding, so a category
  that passed cleanly displays as "Not evaluated" rather than as a pass
- the frontend category grid hides traceability, although the pipeline produces it

## 14. Summary

Radia AI is an enterprise requirements-quality platform that emphasizes explainable
findings, standards grounding, and audit-friendly review workflows. Its architecture
cleanly separates UI, orchestration, review execution, and standards resolution so
the system can evolve without losing traceability of how a result was produced.
