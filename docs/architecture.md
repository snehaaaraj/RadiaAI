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
- `/review/set` - Review multiple requirements parsed from a PDF
- `/review/delta` - Delta review
- `/review/history` - Review history
- `/standards` - Standards catalog
- `/chat` - Document Q&A
- `/search` - Search
- `/documents` - Indexed document inventory and details
- `/settings` - Personalization, Jama account linking, and document ingestion controls
- `/jama-roundtrip` - Jama roundtrip feature entry point (currently a placeholder)

### Frontend behavior

- Persistent UI preferences in local storage
- Theme, accent color, density, motion, sidebar state, and default workspace routing
- Animated page transitions and cards
- Review state preserved across navigation
- Clear review actions to reset stored review state
- Result presentation focused on score, category breakdown, one final recommended requirement, and expandable supporting evidence
- Set review presents results independently for each parsed requirement and reports partial completion
- Chat supports streamed responses as well as the standard response endpoint
- Settings include per-user Jama account linking and role-gated SharePoint ingestion

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
- **prompts**: the consolidated review, delta review and recommendation synthesis prompts
- **skillz**: Skillz package loading, rule parsing and deterministic Skillz checks
- **synthesis**: final recommendation synthesis and its code-enforced validation
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
   score and status. Scores always describe the **original** requirement.
7. Findings are numbered `F1`, `F2`, ... and passed to the final recommendation
   synthesis (see §5.1).
8. The response includes:
   - overall status
   - completion record (see §6)
   - category results
   - findings, each carrying its individual `suggested_rewrite`, source document,
     page/section and excerpt (the evidence)
   - `final_recommendation` - one replacement Description with full provenance
   - the normalized `requirement_text` that was reviewed
   - version metadata
   - review ID

### 5.1 Final recommendation synthesis

Each finding's `suggested_rewrite` fixes only that finding, so several competing
rewrites are produced for one requirement. A second GPT-5 call
(`RecommendationSynthesizer`, prompt `RECOMMENDATION_SYNTHESIS_SYSTEM`) merges them
into **one** Description that can replace the original Jama Description. The
individual findings are kept unchanged as the supporting evidence.

```
Jama requirement → normalize → standards retrieval → consolidated review (findings F1..Fn)
  → scoring (original requirement)
  → Skillz rules (aircraft level) → synthesis + conflict resolution → validation
  → final_recommendation (+ provenance) → UI
```

**Description only.** The Description is extracted from the normalized text; plain
pasted text is treated entirely as the Description. Title and rationale are passed
as context only.

**Source authority is defined by the application, not the LLM.**
`SOURCE_AUTHORITY_LEVEL` assigns Skillz requirements-writing rules level 1 and
standards findings level 2. The prompt states the hierarchy, and the validator
enforces it on every response:

| Rule | Enforcement |
|------|-------------|
| Every finding is accounted for exactly once | missing findings become `not_addressed` |
| Only a loaded Skillz rule can override a finding | an override without one becomes `conflict_unresolved` |
| Only a loaded Skillz rule can resolve a conflict | otherwise the conflict stays `unresolved` |
| Cited rule IDs must exist | invented IDs are removed |
| Final text passes the deterministic Skillz checks | remaining issues are reported |

Any violation triggers one repair round; whatever remains is shown to the user.
Each finding ends up `applied`, `merged_duplicate`, `overridden`,
`conflict_unresolved`, `rejected_unsupported`, `out_of_scope` or `not_addressed`.
Conflicts that no Skillz rule decides are never merged: the original wording is
kept for that aspect, the non-conflicting changes are still applied, and the
conflicting suggestions are shown side by side.

Status: `ready`, `needs_review` (unresolved conflicts, unaddressed findings, or
remaining Skillz check issues), `no_change`, or `failed`. Open items (for example a
verification method still to record) are follow-ups and do not block `ready`.
The recommendation itself is not scored.

### 5.2 Skillz rules

Skillz is the authoritative requirements-writing rule package
(`acr-generator`, WindRunner aircraft-level requirements). It is modelled as a rules
layer, not as another search document: it is not indexed in Azure AI Search.

- `SkillzService` downloads the package zip from SharePoint (`SKILLZ_ZIP_PATH`,
  same Graph credentials as the standards library), caches it for
  `SKILLZ_CACHE_TTL_SECONDS`, and serves the last good copy if a refresh fails.
- The zip is read in memory as data only. Rules are split by ID from
  `references/core-rules.md` (`C1`...), `references/quality-gates.md` (`Q1`...) and
  `references/obligation-form-precedents.md` (`OFP`). The controlled-vocabulary
  lists are read from `scripts/check_acr.py` with `ast.literal_eval`; no package
  file is ever executed.
- Only the rules that govern a single Description (`APPLICABLE_RULE_IDS`) are sent
  to the model. Rules that need ACF/ACFD exports, workbooks or other fields are not.
- Skillz applies only to the levels in `SKILLZ_APPLICABLE_LEVELS` (default
  `aircraft`). Other levels get a standards-only recommendation labelled
  "Skillz not applicable"; if the package cannot be loaded the recommendation is
  labelled "Skillz not applied".
- Every recommendation records the Skillz package, revision, content hash and
  SharePoint URL, plus the full text of every rule it cites.

### Set review

A parsed PDF yields many requirements. Each one runs through the single-requirement
authoring pass independently (including the final recommendation synthesis), and
the results are presented per requirement.

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
- paginated document listing and document detail with indexed chunks
- administrator-only deletion of indexed content (the original source file is not changed)

The chat page supports both a standard response and a server-sent-events streaming
response. Both use retrieval-grounded answers and return citations; the server
returns a fixed no-answer response when the indexed content does not support an
answer.

Ingestion extracts text, chunks it, embeds it with `text-embedding-3-large`, and
indexes it into Azure AI Search. File hashes are recorded so unchanged documents
are not re-embedded.

Ingestion runs on demand via `POST /api/v1/ingest` - it is deliberately not run at
startup, which keeps cold starts viable on serverless hosting. The review pipeline
depends on this index being populated: with an empty index, reviews return
`no_standards_context` rather than findings.

## 10.1 MCP (Model Context Protocol) engineering-data chat integration

Chat can optionally ground an answer in live engineering-system data (Jama today;
Jira/Confluence remain on hold) by calling read-only tools on the separately
deployed [`mcp-radia`](../mcp-radia/README.md) server, instead of relying only on
the indexed-document RAG pipeline above. **Disabled by default** (`MCP_ENABLED=false`);
when disabled, chat behaves exactly as described in section 10.

The two pipelines are never mixed. Users opt in per conversation: a chat message
starting with `/radiaai` switches the conversation to **RadiaAI mode**
(`ChatRequest.mode="radiaai"`), where document retrieval is skipped and answers come
only from mcp-radia tools; `/exit` returns to the standards checker (the default
`mode="standards"`, which never calls tools). `/radiaai <question>` switches and asks
in one step. The mode is derived from the command turns in the persisted conversation
([`frontend/src/utils/chatMode.ts`](../frontend/src/utils/chatMode.ts)), and only turns
since the last command are sent as history, so standards answers never leak into a
live-data question (or vice versa). In RadiaAI mode, if MCP is disabled or unreachable,
a fixed "unavailable" message is returned instead of an ungrounded model answer.

### Request flow

```
Browser (signed-in user)
  -> POST /api/v1/chat[/stream]  (Entra ID token, enforced as today)
  -> mode="standards" (default): RAG retrieval + grounded answer, no tools
  -> mode="radiaai" (/radiaai ... /exit): no retrieval; bounded tool-calling loop
       -> MCPClientAdapter discovers tools via mcp-radia's tools/list
       -> intersects with the server-side allowlist (MCP_ALLOWED_TOOLS)
       -> validates the model's requested arguments against the tool's own JSON Schema
          (list_related_items is narrowed to system="jama" for chat)
       -> calls mcp-radia over Streamable HTTP (service bearer token + internal network)
       -> mcp-radia calls Jama as the signed-in user's own linked account, if linked
          (jama_* tools and list_related_items alike)
  -> grounded answer (+ sources, used_mcp) returned to the chat UI, unchanged SSE/JSON shape
```

Key modules: [`app/services/mcp/client.py`](../backend/app/services/mcp/client.py)
(allowlist + schema validation + session reuse), [`transport.py`](../backend/app/services/mcp/transport.py)
(JSON-RPC/Streamable HTTP, built on `httpx` rather than the official `mcp` SDK - see
the module docstring for why), and [`orchestrator.py`](../backend/app/services/mcp/orchestrator.py)
(the bounded tool-calling loop: `MCP_MAX_TOOL_ITERATIONS` sequential calls, `MCP_MAX_TOTAL_SECONDS`
overall deadline, never executes a tool outside the allowlist regardless of what the model requests).

### Identity and credentials

- The chat endpoint's existing Entra ID authentication and `Radia.User`/`Radia.Admin`
  authorization are unchanged and still enforced on every request.
- A signed-in user's own linked Jama OAuth credentials (the same link used by the
  Jama Requirement Reviewer, `JamaAccountService`) are forwarded to mcp-radia as
  per-request headers, so Jama itself enforces that user's permissions. mcp-radia
  has no shared Jama account at all: over HTTP it holds only the Jama base URL, and
  a call without the per-user headers fails asking the user to link their Jama
  account in RadiaAI Settings. (Run locally over stdio, mcp-radia instead uses the
  developer's own `JAMA_CLIENT_ID`/`JAMA_CLIENT_SECRET`; those are never read over
  HTTP.)
- mcp-radia itself requires a shared service-to-service bearer token
  (`MCP_SERVICE_TOKEN` / mcp-radia's `MCP_RADIA_SERVICE_TOKEN`) on every request.
  **Deployment-dependent network exposure:** the Azure Container Apps template
  ([`infra/mcp-radia.bicep`](../infra/mcp-radia.bicep)) restricts ingress to the
  private network, so the bearer token is defense-in-depth on top of network
  isolation. The **Vercel deployment path below has no such network boundary**
  - mcp-radia's URL is reachable from the public internet, and the bearer
    token is the *only* thing standing between the internet and whatever Jama
    data it is configured to reach. This tradeoff is accepted for demo
    purposes only; see the Vercel walkthrough below for what that implies.
- Jira and Confluence linking is **on hold**: the Settings page shows a disabled
  "Link Atlassian account" placeholder, and no Jira/Confluence tools are in the
  default allowlist.

### Failure handling

MCP failures (disabled, unreachable, timed out, disallowed tool, invalid
arguments) are caught in the orchestrator and surfaced as a plain-language
answer or tool-result message - never a raw exception, stack trace, or
unhandled 500 - and never stop the rest of chat from working.

## 11. Configuration and deployment

Runtime configuration is controlled through environment variables.

Key services:

- Azure OpenAI
- Azure AI Search
- Azure Blob Storage
- Microsoft Entra ID
- SharePoint
- mcp-radia (optional, disabled by default - see 10.1 and the deployment walkthroughs below)

The project supports:

- local backend development with Uvicorn
- local frontend development with Vite
- frontend deployment to Vercel from the repo root (`vercel.json`)
- mcp-radia deployed either to **Vercel** (demo path, bearer-token-only - see below)
  or to **Azure Container Apps with internal-only ingress** for a production
  posture ([`infra/mcp-radia.bicep`](../infra/mcp-radia.bicep))

### MCP deployment walkthrough - Vercel (demo)

This path mirrors how the backend itself is already deployed to Vercel
(`backend/api/index.py` + `backend/vercel.json`): mcp-radia gets its own
sibling `api/index.py` + `vercel.json`, deployed as its **own, separate**
Vercel project (own URL, own environment variables, own dependency set - it
never shares a build or a Python environment with the backend).

mcp-radia's Streamable HTTP app runs in the MCP SDK's **stateless** mode for
this path specifically: a serverless function gives no guarantee that two
requests reach the same warm instance, so no in-memory session could survive
between them regardless of mode. Each request is independently self-contained
(no `initialize` handshake is required before a tool call) - see
[`mcp_radia/asgi.py`](../mcp-radia/mcp_radia/asgi.py) for exactly what differs
from the Azure/local path, including a Host-header check that had to be
disabled specifically for this mode (a public domain is not loopback, and the
SDK's auto-protection assumes it is).

**Security tradeoff, stated plainly:** unlike the Container Apps path, Vercel
has no "internal-only" networking option on this project's plan. mcp-radia's
URL is publicly reachable; `MCP_RADIA_SERVICE_TOKEN` is the only access
control. Anyone who obtains that token (e.g. a repository/environment-variable
leak, a compromised backend) can call mcp-radia directly - bypassing
Microsoft Entra ID sign-in and the backend entirely - and reach whatever Jama
data mcp-radia is configured with. This is accepted here only because the
goal is a demo with a scoped Jama trial instance, not a production rollout of
real, sensitive requirements data. Do not point a demo deployment of this kind
at a production Jama tenant.

Steps:

1. **Deploy mcp-radia to its own Vercel project**, with the project root set
   to the `mcp-radia/` directory (same idea as the existing backend/frontend
   Vercel projects, which are rooted at `backend/` and the repo root
   respectively). Set these as that Vercel project's environment variables
   (not `.env` - Vercel never sees `.env`, same as the backend today):
   ```bash
   MCP_RADIA_SERVICE_TOKEN=<generate: openssl rand -hex 32>
   MCP_RADIA_ENVIRONMENT=production
   JAMA_BASE_URL=https://yourorg.jamacloud.com      # your Jama trial instance
   ```
   No Jama credentials go here: each chat user links their own Jama account in
   RadiaAI Settings, and the backend forwards it on every MCP request.
   Deploy. Note the resulting URL, e.g. `https://mcp-radia-yourname.vercel.app`.
2. **Configure the backend's MCP client** in the backend's own Vercel project
   environment variables (or `backend/.env` for local testing):
   ```bash
   MCP_ENABLED=true
   MCP_SERVER_URL=https://mcp-radia-yourname.vercel.app/mcp
   MCP_SERVICE_TOKEN=<same value as mcp-radia's MCP_RADIA_SERVICE_TOKEN>
   MCP_ALLOWED_TOOLS=jama_get_item,jama_search,jama_get_children,jama_list_projects,list_related_items
   ```
   Redeploy the backend (or restart it locally) so the new variables take effect.
3. **Verify the handshake and tool discovery**: type `/radiaai` in the chat, then ask a
   Jama-shaped question (e.g. "What does Jama item 12345 say?"). A `mcp_tools_discovered`
   log line confirms the handshake; `mcp_tool_iteration_complete` confirms a
   tool call executed.
4. **Test an authenticated read-only request** end-to-end: sign in to Radia AI
   with your Microsoft account (unchanged - this still gates the whole app),
   link your Jama account in Settings, and ask about a Jama item you can read.
   The response's `used_mcp`/`sources` fields (and the chat UI's "Engineering
   data" chip) confirm the tool path was used.
5. **Disable MCP without disrupting ordinary chat**: set `MCP_ENABLED=false`
   on the backend and redeploy/restart. Chat immediately reverts to
   document-only RAG answers; nothing else changes.
6. **Roll back safely**: mcp-radia is an independent Vercel project - rolling
   back its deployment (Vercel's own "Promote to Production" / instant
   rollback on a prior deployment) never requires touching the backend or
   frontend. Rolling the backend back to `MCP_ENABLED=false` is likewise an
   instant, data-free rollback of just this feature.

### MCP deployment walkthrough - Azure Container Apps (production posture)

1. **Start mcp-radia locally** (for development/testing before any cloud deployment):
   ```bash
   cd mcp-radia
   cp .env.example .env   # fill in JAMA_BASE_URL + a generated MCP_RADIA_SERVICE_TOKEN
   pip install -e ".[dev]"
   mcp-radia http          # http://127.0.0.1:8081/mcp
   ```
2. **Start the backend and frontend** as usual (see the repo root README).
3. **Configure the backend's MCP client** in `backend/.env`:
   ```bash
   MCP_ENABLED=true
   MCP_SERVER_URL=http://127.0.0.1:8081/mcp
   MCP_SERVICE_TOKEN=<same value as mcp-radia's MCP_RADIA_SERVICE_TOKEN>
   MCP_ALLOWED_TOOLS=jama_get_item,jama_search,jama_get_children,jama_list_projects,list_related_items
   ```
4. **Verify the handshake and tool discovery**: start the backend, then type
   `/radiaai` in the chat, then ask a Jama-shaped question (e.g. "What does Jama item 12345 say?"). A
   `mcp_tools_discovered` log line confirms the handshake; `mcp_tool_iteration_complete`
   confirms a tool call executed.
5. **Test an authenticated read-only request** end-to-end: sign in, link a Jama
   account in Settings, and ask about a Jama item you know you can read in Jama.
   The response's `used_mcp`/`sources` fields (and the chat UI's "Engineering data"
   chip) confirm the tool path was used.
6. **Disable MCP without disrupting ordinary chat**: set `MCP_ENABLED=false` (or
   remove `MCP_SERVER_URL`/`MCP_SERVICE_TOKEN`) and restart the backend. Chat
   immediately reverts to document-only RAG answers; nothing else changes.
7. **Deploy mcp-radia to Azure Container Apps**:
   ```bash
   az deployment group create \
     --resource-group <rg> \
     --template-file infra/mcp-radia.bicep \
     --parameters containerImage=<registry>/mcp-radia:<tag> \
                  mcpServiceToken=<generated secret> \
                  jamaBaseUrl=https://yourorg.jamacloud.com
   ```
   The template defaults to internal-only ingress - it is never reachable from
   the public internet. **Known gap:** the backend is currently deployed to
   Vercel, which cannot reach a Container Apps internal endpoint directly; until
   the backend is also network-integrated with mcp-radia (e.g. moved onto Azure
   with VNet integration, or fronted by an authenticated private gateway), this
   path requires the backend to also run somewhere network-reachable from
   mcp-radia's internal endpoint. Use the Vercel demo path above if both
   services should simply be reachable from each other with no extra
   infrastructure.
8. **Restart/roll back safely**: mcp-radia is independent of the backend and
   frontend - restarting or rolling back its Container App (e.g. `az containerapp
   revision` commands) does not require redeploying either. Rolling the backend
   back to a build with `MCP_ENABLED=false` (or simply flipping that one setting)
   is a safe, instant rollback of the chat-facing feature with no data migration.

## 12. Security and operational notes

- Secrets are loaded from `backend/.env` (backend-only; frontend `.env` files hold only
  public `VITE_*` build-time values)
- Every non-public endpoint requires a validated Microsoft Entra ID token and a Radia
  app role ([authentication.md](./authentication.md))
- Jama is accessed as each signed-in user's own linked Jama account
- The MCP chat integration is disabled by default, allowlists tools server-side,
  validates arguments against each tool's schema, and requires a bearer token on
  every request to mcp-radia; the production (Azure) deployment also restricts
  mcp-radia's network ingress, while the Vercel demo deployment relies on the
  bearer token alone - see section 10.1 for that explicit tradeoff
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
| Document inventory and management | Implemented | `GET /api/v1/documents` supports paging, filtering, and sorting; `GET /api/v1/documents/{id}` returns metadata and chunks; Admin can delete indexed content without changing the source file. |
| Document-oriented workflows | Implemented | SharePoint/file ingestion, search, standard and streamed chat, document inventory, detail, and administrator-only indexed-content deletion are available. |
| Dependency health probes | Implemented | `GET /health/live` is a lightweight process check; `GET /health/ready` (and the legacy `GET /health` alias) performs bounded, cached, real connectivity probes against Azure OpenAI, Azure AI Search, and Blob Storage (required) plus SharePoint and Jama (optional-but-configured), returning HTTP 503 only when a required dependency is down. |
| Microsoft Entra ID authentication and authorization | Implemented | SPA sign-in with MSAL; API validates Entra access tokens (RS256/JWKS, issuer, audience, expiry, tenant, scope) and enforces `Radia.User` / `Radia.Admin` app roles on every non-public endpoint. Local/test environments may use a synthetic user; deployed environments fail closed. See [authentication.md](./authentication.md). |
| Per-user Jama access | Implemented | Each user links their own Jama API credentials (encrypted at rest); all Jama calls run as that user so Jama enforces their project permissions. Review history is private per user. |
| Workspace and launchpad UX | Implemented | Provides the current frontend navigation and review workflows. |
| MCP chat integration (Jama) | Implemented, disabled by default | Bounded tool-calling loop over a separately deployed `mcp-radia` server; server-side allowlist + schema validation + per-user Jama credential forwarding. Jira/Confluence tools and Atlassian account linking are on hold (Settings shows a disabled placeholder). Deployable to Vercel (demo; bearer-token-only, no network isolation - see section 11) or Azure Container Apps (production posture; internal-only ingress). |

## 14. Summary

Radia AI is an enterprise requirements-quality platform that emphasizes explainable
findings, standards grounding, and audit-friendly review workflows. Its architecture
cleanly separates UI, orchestration, review execution, and standards resolution so
the system can evolve without losing traceability of how a result was produced.
