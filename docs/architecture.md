# Radia AI Architecture

Radia AI is an explainable requirements-engineering platform for aerospace and systems teams. It combines a React frontend with a FastAPI backend to support requirement quality review, delta review, standards lookup, review history, and document-oriented workflows.

> **Architecture status:** This document describes the target architecture. The
> implementation-status table in §13 identifies capabilities that are currently
> implemented, in progress, or planned.

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

- `/` - Launchpad
- `/radia-ai` - Radia AI Resources
- `/workspace` - Main application workspace
- `/review/requirement` - Single requirement review
- `/review/delta` - Delta review
- `/review/history` - Review history
- `/standards` - Standards catalog
- `/chat` - Document Q&A
- `/search` - Search
- `/documents` - Documents
- `/settings` - Personalization controls

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

Single review is an **authoring** pass: it flags violations and proposes replacement text.

1. The user submits one requirement.
2. The orchestrator normalizes the input (fielded Jama text is flattened to
   Title / Description / Rationale).
3. `LLMReviewEnhancer` retrieves standards context from Azure AI Search, using
   source-diversified retrieval so several documents can be cited.
4. One consolidated GPT-5 call produces findings across all four scored categories.
5. Findings are enriched with standards references and SharePoint URLs.
6. Category scores are derived from the findings and averaged into an overall
   score and status.
7. The response includes:
   - overall status
   - completion record (see §6)
   - category results
   - findings, each carrying a `suggested_rewrite` (the changeset)
   - version metadata
   - review ID

### Set review

A parsed PDF yields many requirements. Each one runs through the single-requirement
authoring pass independently, and the results are presented per requirement.

### Delta review

Delta review is a **verification** pass. Its input is a requirement that a single
or set review already caused to be revised, so it scores the revision instead of
asking for another one.

1. The system compares baseline and updated requirement sets.
2. It identifies:
   - new requirements
   - modified requirements
   - deleted requirements
3. Only changed requirements are re-reviewed. Each is paired with the baseline
   text it replaces (`RequirementRevision`), so the model can confirm the revision
   resolved the earlier findings rather than re-raising them.
4. Scoring uses `DELTA_REVIEW_SYSTEM`, which explicitly forbids proposing new
   requirement text. The parser also drops any `suggested_rewrite` the model
   returns anyway, so the contract holds even if prompt compliance slips.
5. Results are aggregated into a delta response with a change summary and a
   run-level completion record.

### How baseline and updated requirements are paired

| Input | Pairing key |
|-------|-------------|
| Requirement carries an ID | that ID |
| Requirement has no ID | its **position** - the Nth unidentified baseline requirement pairs with the Nth unidentified updated requirement, labelled `Requirement N` |

Position is the only usable signal for unidentified requirements. Keying them by
their text cannot work, because a revision changes the text by definition: the
revision would never match its baseline, so every edit would be reported as a
deletion plus an addition and scored with no previous version to compare against.
That is exactly the paste-the-original, paste-the-revision workflow this page
exists for.

Because a delta-reviewed requirement has already been corrected against the
standards, its scores are expected to be high, and an empty findings list is the
normal outcome for a good revision.

## 6. Review completion contract

The review *verdict* and the review *process outcome* are separate fields, because
an empty findings list is ambiguous on its own - it means either "this requirement
is clean" or "the engine never ran".

Every review response carries a `completion` record:

| Field | Meaning |
|-------|---------|
| `status` | `complete`, `partial` (batch: some items evaluated), or `failed` |
| `reason` | machine-readable cause, null when complete |
| `message` | reviewer-facing explanation |

Failure reasons are raised by the specific stage that broke:

- `review_engine_unavailable` - no LLM enhancer could be constructed
- `no_standards_context` - retrieval returned nothing to review against
- `retrieval_failed` - Azure AI Search errored
- `llm_call_failed` - the GPT-5 call errored
- `invalid_llm_response` - the response was not parsable JSON of the expected shape

When a review does not complete, `overall` is `Not Evaluated` and findings and
category results are empty. The frontend renders the failure notice in place of
the score, so an unevaluated requirement is never displayed as a passing one.

## 7. Reviewer modules

Requirement analysis happens in one consolidated GPT-5 call per requirement
(`app/prompts/review_prompts.py`). Two prompts share the same four scored
categories:

- `CONSOLIDATED_REVIEW_SYSTEM` - authoring review (single and set review); proposes rewrites
- `DELTA_REVIEW_SYSTEM` - verification review (delta review); proposes nothing

The scored categories are:

- **Language**: mandatory modal usage, banned words, ambiguous wording, passive voice
- **Structure**: one requirement per statement, human-judgment language, EARS syntax, requirement level
- **Verifiability**: quantitative limits, operating conditions, verification method
- **Certification**: DO-178C / DO-254 / ARP4754A alignment, verification methods, safety language, DAL

`ReviewCategory` in `models/review_models.py` is the single source of truth for
this list. The prompt, the response parser, the orchestrator's category scoring
and the UI grid all derive from it, so a category cannot be produced by one layer
and silently dropped by another. Traceability is deliberately out of scope.

### Category scoring

A completed review emits a `CategoryResult` for **every** category, not only the
ones that produced findings. Each result carries a numeric `score` (0-10) and the
verdict band that score falls in:

- findings in a category → the score is earned down from 10 by the findings
- no findings in a category → a full `10.0`, `Acceptable`

Omitting clean categories would make "checked and clean" indistinguishable from
"never checked". A review that did not complete emits no category results at all,
because nothing was scored (§6).

The category grid mirrors this on the client: it always renders the four scored
categories, showing "Not scored" for any the payload omits rather than dropping
the tile or inventing a passing value. Persisted review results are keyed by a
schema version so a result cached by an older build cannot be rendered against
the current scorecard.

### From findings to number

Scores are computed on the backend (`utils/review_scoring.py`) from the findings
themselves, not looked up from a category or a status. Every category starts at
`10.0` and loses points:

| Severity of the worst finding | Penalty |
|-------------------------------|---------|
| Low | 2.5 |
| Medium | 4.0 |
| High | 6.0 |
| Critical | 8.0 |

Every additional finding in the same category costs **half** its own penalty:
repeat problems compound, but with diminishing weight, since the first defect is
what characterises the category. Scores are floored at `0`.

The Low penalty is deliberately large enough that *any* open finding drops a
category below the Acceptable threshold — a category with an open finding must
never present itself as clean — and the High penalty drops it below the revision
threshold, keeping the derived band consistent with the severity taxonomy.

### From number to verdict

| Average score | Verdict |
|---------------|---------|
| ≥ 8.0 | Acceptable |
| ≥ 5.0 | Revision Recommended |
| < 5.0 | Unacceptable |
| nothing scored | Not Evaluated |

**The overall score is the arithmetic mean of the scored category scores, and the
overall verdict is the band that mean falls in.** For example `10, 10, 10, 3.5`
averages to `8.375` → `Acceptable`: one weak sub-category lowers the score
without on its own condemning an otherwise strong requirement. A requirement that
is broadly weak still fails, because the mean itself falls into the lower bands.

Categories that carry no score are excluded from the mean rather than counted as
zero; when nothing was scored at all the verdict is `Not Evaluated` and the page
renders the incomplete notice instead of a score (§6).

Severity is deliberately **not** applied again at aggregation time. It is already
baked into the category scores being averaged, so penalising it a second time
would double-count it. The client (`utils/reviewQuality.ts`) averages the same
category scores for display, falling back to a status-based approximation only
for older stored payloads that predate the numeric field.

The reviewer modules registered with the orchestrator
(`reviewers/consolidated.py`, one per category) carry no rule logic.
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

Completed reviews are stored in Azure Blob Storage for durability.

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

Review history persists across deployments and serverless invocations via Azure Blob Storage.

## 10. Document and RAG surfaces

The target architecture includes these document-centric workflows:

- chat over indexed content
- document search (keyword / vector / hybrid)
- document ingestion (SharePoint or uploaded file)
- document listing

Ingestion extracts text, chunks it, embeds it with `text-embedding-3-large`, and
indexes it into Azure AI Search. File hashes are recorded so unchanged documents
are not re-embedded.

Ingestion runs on demand via `POST /api/v1/ingest` - it is deliberately not run at
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

| Capability | Status | Current scope and remaining work |
|---|---|---|
| Standards-grounded requirement, set, and delta review | Implemented | Includes completion reporting, version metadata, and standards reference resolution. |
| Review history | Implemented | Persists review history and dispositions in Azure Blob Storage. |
| Document ingestion and search | Implemented | Supports SharePoint and file-upload ingestion, chunking, embedding, and keyword/vector/hybrid search. |
| Chat over indexed documents | Implemented | Provides grounded RAG responses, citations, streaming, no-answer behavior, and search-failure handling. |
| Document listing and document management | Planned | `GET /api/v1/documents` currently returns an empty placeholder response; document detail and deletion are not implemented. |
| Document-oriented workflows | In progress | Ingestion, search, and chat are available; document inventory and management workflows remain incomplete. |
| Dependency health probes | Implemented | `GET /health/live` is a lightweight process check; `GET /health/ready` (and the legacy `GET /health` alias) performs bounded, cached, real connectivity probes against Azure OpenAI, Azure AI Search, and Blob Storage (required) plus SharePoint and Jama (optional-but-configured), returning HTTP 503 only when a required dependency is down. |
| Microsoft Entra ID authentication and authorization | Planned | Local development uses a synthetic user. Production JWT/JWKS validation, issuer and audience checks, and role extraction are not implemented. |
| Workspace and launchpad UX | Implemented | Provides the current frontend navigation and review workflows. |

## 14. Summary

Radia AI is an enterprise requirements-quality platform that emphasizes explainable
findings, standards grounding, and audit-friendly review workflows. Its architecture
cleanly separates UI, orchestration, review execution, and standards resolution so
the system can evolve without losing traceability of how a result was produced.
