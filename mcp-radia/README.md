# mcp-radia

A standalone [Model Context Protocol](https://modelcontextprotocol.io) server that will expose
RadiaAI's engineering systems of record — **Jama, Jira, Confluence and Genesys** — through one
read-only MCP surface, as a digital-thread integration layer.

> **Status: Phase 4 — feature-complete for this pass.** Jama, Jira and Confluence are connected
> read-only, with cross-system linking on top: **7 tools**. GENESYS is a
> [placeholder](#vitech-genesys--placeholder) and registers no tools.

## Relationship to the rest of this repo

`mcp-radia/` is deliberately **independent** of `backend/` and `frontend/`:

- Its own `pyproject.toml`, `.env`, tests and virtualenv.
- It **never imports** from `app` or `radia_ai`, and nothing in `backend/` imports from it.
- It reads only `mcp-radia/.env` — never `backend/.env` or the repo-root `.env`.

The backend's existing Jama connector was read for inspiration, but the connector here is a fresh
implementation. The RadiaAI backend talks to this server as an MCP client over Streamable HTTP —
see [`docs/architecture.md`](../docs/architecture.md) for how that integration is wired end to end,
and [Deploy](#deploy) below for running this server itself.

## Requirements

- Python 3.12+ (developed against 3.13)

## Install

Use a virtualenv dedicated to this package — do not install it into the backend's environment.

```bash
cd mcp-radia
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -e ".[dev]"
```

> **VS Code:** select `mcp-radia/.venv` as the interpreter when working in this folder, otherwise
> the editor resolves imports against the backend's environment and reports `mcp`, `pydantic` etc.
> as missing.

## Configure

```bash
cp .env.example .env
```

The server runs against an empty `.env` — every setting has a working default, and an
unconfigured connector still lists its tools, failing per-call with a message naming the variable
to set. Server settings are prefixed `MCP_RADIA_`:

| Variable                | Default     | Purpose                                        |
| ----------------------- | ----------- | ---------------------------------------------- |
| `MCP_RADIA_ENVIRONMENT` | `local`     | `local`/`development` ⇒ console logs, else JSON |
| `MCP_RADIA_LOG_LEVEL`   | `INFO`      | `DEBUG`…`CRITICAL`                             |
| `MCP_RADIA_HOST`        | `127.0.0.1` | HTTP transport bind address                    |
| `MCP_RADIA_PORT`        | `8081`      | HTTP transport bind port                       |
| `MCP_RADIA_HTTP_PATH`   | `/mcp`      | Path the HTTP transport is mounted at           |
| `MCP_RADIA_SERVICE_TOKEN` | *empty*   | Bearer token the HTTP transport requires on every request — **required** to start `http` |

Port `8081` is the default specifically so it does not collide with the RadiaAI backend on `8000`.

`MCP_RADIA_SERVICE_TOKEN` is a shared secret between this server and its one legitimate caller,
the RadiaAI backend — not a per-user credential. Generate one with `openssl rand -hex 32` and
configure the identical value as the backend's `MCP_SERVICE_TOKEN` (see
[`docs/architecture.md`](../docs/architecture.md)). The `http` subcommand refuses to start without
it: an empty token almost always means it was forgotten, not that auth should be skipped.

### Jama (`JAMA_*`)

| Variable               | Default | Purpose                                          |
| ---------------------- | ------- | ------------------------------------------------ |
| `JAMA_BASE_URL`        | *empty* | Instance root, e.g. `https://org.jamacloud.com`  |
| `JAMA_API_VERSION`     | `v1`    | REST version path segment                        |
| `JAMA_TIMEOUT_SECONDS` | `20`    | Per-request timeout                              |
| `JAMA_VERIFY_SSL`      | `true`  | Only disable for a self-signed test instance     |
| `JAMA_CLIENT_ID`       | *empty* | **stdio only** - *your own* Jama OAuth client id |
| `JAMA_CLIENT_SECRET`   | *empty* | **stdio only** - *your own* Jama OAuth secret    |

**There is no shared Jama account.** Every Jama call - the `jama_*` tools and the Jama side of
`list_related_items` - runs as an individual user via OAuth client-credentials, so Jama itself
enforces what that person can read:

- **HTTP (deployed; used by RadiaAI chat).** The backend forwards the signed-in user's own linked
  Jama account (linked in the RadiaAI UI under Settings - the same link the Jama Requirement
  Reviewer uses) as the `X-Radia-Jama-Client-Id` / `X-Radia-Jama-Client-Secret` headers. A call
  without them fails with "Link your Jama account in RadiaAI Settings". `JAMA_CLIENT_ID` /
  `JAMA_CLIENT_SECRET` are never read over HTTP. See
  [`mcp_radia/tools/_identity.py`](mcp_radia/tools/_identity.py).
- **stdio (local GitHub Copilot / Claude Desktop).** Set `JAMA_CLIENT_ID` / `JAMA_CLIENT_SECRET`
  to *your own* Jama OAuth client. Only the stdio entry point loads them.

### Atlassian Cloud — Jira + Confluence (`ATLASSIAN_*`)

| Variable                    | Default | Purpose                                      |
| --------------------------- | ------- | -------------------------------------------- |
| `ATLASSIAN_SITE_URL`        | *empty* | Site root, e.g. `https://org.atlassian.net`  |
| `ATLASSIAN_EMAIL`           | *empty* | Account email owning the token               |
| `ATLASSIAN_API_TOKEN`       | *empty* | API token (**not** the account password)     |
| `ATLASSIAN_TIMEOUT_SECONDS` | `20`    | Per-request timeout                          |
| `ATLASSIAN_VERIFY_SSL`      | `true`  | Verify TLS certificates                      |

**Jira and Confluence share one credential set.** That is how Atlassian Cloud works: both products
sit under the same site and accept the same API token, and the owning account's product
permissions decide what is readable. Confluence is reached at `{site}/wiki` automatically — don't
put `/wiki` in `ATLASSIAN_SITE_URL`.

Create a token at
[id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
Prefer a dedicated service account over a person's credentials.

### Vitech GENESYS — placeholder

**Not implemented.** No `genesys_*` tools are registered, and `list_related_items` returns a note
rather than results for `system="genesys"`.

This is Vitech GENESYS, the MBSE tool now owned by Zuken — **not Genesys Cloud CX**, the
contact-centre platform that shares the name. Its REST contract could not be verified: Vitech's
public API docs (the Getting Started PDF, the AdminTools help page) now redirect to Zuken
marketing pages, and the reference sits behind a customer login or each instance's own Swagger.

Rather than ship a speculative client, [`connectors/genesys.py`](mcp_radia/connectors/genesys.py)
keeps only `GenesysSettings` (so a `.env` written today stays valid), the model shapes the real
connector should return, and a client whose operations raise `ConnectorNotImplementedError`.

**To implement:** enable Swagger in *AdminTools → Configure REST API*, read the real contract from
its Swagger UI, and build against it. The data model to expect: a **project** is a model
repository; an **entity** is the unit of content (Requirement, Component, Function, …) with
free-form **attributes** and typed **relationships** — those relationships being exactly what the
linking layer wants.

## Run

Two transports share one tool registry.

### stdio (default)

For local MCP clients that launch the server as a subprocess:

```bash
mcp-radia              # or: mcp-radia stdio
python -m mcp_radia    # equivalent, no console script needed
```

Under stdio, **stdout is the JSON-RPC channel**. All logging therefore goes to **stderr** — see
[`mcp_radia/logging.py`](mcp_radia/logging.py). Anything printed to stdout will corrupt the
protocol stream and the client will drop the connection.

To register with Claude Desktop, add to its `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "radia": {
      "command": "/absolute/path/to/mcp-radia/.venv/bin/mcp-radia",
      "args": ["stdio"]
    }
  }
}
```

(On Windows use `...\\.venv\\Scripts\\mcp-radia.exe`.)

### Streamable HTTP

For running as a deployed network service:

```bash
mcp-radia http                              # http://127.0.0.1:8081/mcp
mcp-radia http --host 0.0.0.0 --port 9000   # CLI flags override the environment
```

`MCP_RADIA_SERVICE_TOKEN` must be set before this starts — see the table above. Every request must
carry it as `Authorization: Bearer <token>`; anything else gets a `401`, logged as
`mcp_service_auth_rejected`.

### Inspect it

```bash
npx @modelcontextprotocol/inspector mcp-radia stdio
```

Phase 0 will show a successful connection and an empty tool list. That is the expected result.

## Test

```bash
cd mcp-radia
pytest                  # all tests
pytest -m unit          # unit tests only
ruff check . && ruff format --check . && mypy mcp_radia
```

No test in this suite touches the network, and that is **enforced, not assumed**: an autouse
fixture in [`tests/conftest.py`](tests/conftest.py) fails any test that resolves a hostname or
opens a non-loopback socket. Connector tests serve canned responses through
`httpx2.MockTransport`; tool tests drive a **real MCP client session over in-memory streams**, so
handshake, schema generation, `tools/call` and error translation are all exercised for real
without binding a port or spawning a process.

There is currently **no CI workflow** for this package — the repo's existing workflows are
path-filtered to `backend/**` and `frontend/**`, so they neither run against nor are affected by
this directory. Run the commands above locally before committing.

## Layout

```
mcp-radia/
├── mcp_radia/
│   ├── auth.py              # bearer service-token check for the HTTP transport
│   ├── cli.py              # argparse entrypoint; stdio + http subcommands
│   ├── config.py           # pydantic-settings, MCP_RADIA_* prefix
│   ├── logging.py          # structlog -> stderr
│   ├── server.py           # build_server(): constructs the MCPServer
│   ├── connectors/         # one module per external system
│   │   ├── errors.py       # shared ConnectorError hierarchy + remote-message extraction
│   │   ├── retry.py        # bounded 429 backoff with jitter
│   │   ├── text.py         # HTML / ADF -> plain text
│   │   ├── atlassian.py    # shared Cloud settings + HTTP base
│   │   ├── jama.py         # Jama settings, models, async client
│   │   ├── jira.py         # Jira Cloud v3
│   │   ├── confluence.py   # Confluence Cloud v2 + v1 search
│   │   └── genesys.py      # Vitech GENESYS - placeholder, not implemented
│   ├── linking/            # cross-system tracing, no datastore
│   │   ├── models.py
│   │   ├── references.py   # finds item keys written into prose
│   │   └── service.py      # queries every connector live
│   └── tools/              # single registration point for every MCP tool
│       ├── _guard.py       # ConnectorError -> ToolError, READ_ONLY annotation
│       ├── _identity.py    # per-user Jama credential passthrough from request headers
│       ├── jama.py
│       ├── jira.py
│       ├── confluence.py
│       ├── genesys.py      # registers nothing (placeholder)
│       └── linking.py
└── tests/
```

Connectors know nothing about MCP; the `tools/` layer knows nothing about HTTP. The only thing
crossing that line is the `ConnectorError` hierarchy, which `tools/jama.py` translates into
`ToolError` so the client gets an actionable message.

The importable package is `mcp_radia` (underscore) inside the `mcp-radia` project directory, since
a hyphen is not legal in a Python package name.

## Deploy

Two deployment shapes are supported, both documented end to end in
[`docs/architecture.md`](../docs/architecture.md) section 11:

### Vercel (demo)

Mirrors how the RadiaAI backend itself deploys to Vercel: `api/index.py` and
`vercel.json` in this directory build a **stateless** Streamable HTTP ASGI app
(see [`mcp_radia/asgi.py`](mcp_radia/asgi.py)) as mcp-radia's own, separate
Vercel project. Set `MCP_RADIA_SERVICE_TOKEN` and the `JAMA_*` variables as
that project's environment variables (not `.env` — Vercel never sees it).

**This path has no network isolation** — Vercel gives the deployment a public
URL, and `MCP_RADIA_SERVICE_TOKEN` is the *only* access control in front of
it. Accepted for a demo against a scoped Jama trial instance only; see
`docs/architecture.md` section 10.1 for the explicit tradeoff. Do not point a
Vercel deployment of this kind at a production Jama tenant.

### Azure Container Apps (production posture)

This server is meant to run as its own service, reachable only from the RadiaAI backend — never
from the browser or the public internet.

```bash
docker build -t mcp-radia .
docker run --rm -p 127.0.0.1:8081:8081 --env-file .env mcp-radia
```

The [`Dockerfile`](Dockerfile) runs `mcp-radia http` (stateful mode — a session persists in
memory across requests, since this is a long-running process) and binds to `0.0.0.0:8081`
*inside* the container; the container itself should only ever be reachable on a private
network — map it to a loopback address locally (as above), and use internal-only ingress in
Azure Container Apps (see [`infra/mcp-radia.bicep`](../infra/mcp-radia.bicep)).

Two things are required before the HTTP transport will start at all:

1. `MCP_RADIA_SERVICE_TOKEN` — the shared bearer token described above.
2. A network that the backend can reach but the public internet cannot.

Neither TLS termination nor certificate handling lives in this server; terminate TLS at the
platform (Container Apps ingress) in front of it.

`register_tools()` in [`mcp_radia/tools/__init__.py`](mcp_radia/tools/__init__.py) is the one place
that lists the server's entire surface area. Each phase adds its registration call there.

## Roadmap

| Phase | Scope                                                              | Status |
| ----- | ------------------------------------------------------------------ | ------ |
| 0     | Scaffold: server, config, logging, both transports, smoke tests     | ✅ done |
| 1     | Jama connector — `jama_get_item`, `jama_search`                     | ✅ done |
| 2     | Jira + Confluence — `jira_get_issue`, `jira_search`, `confluence_*` | ✅ done |
| 3     | GENESYS                                                             | ⏸️ placeholder |
| 4     | `list_related_items(system, item_id)` cross-system linking          | ✅ done |
| 5     | Jama hierarchy — `jama_get_children`; tool descriptions tuned for selection | ✅ done |

### Deliberate non-goals for this pass

- **Read-only.** No tool creates, updates or deletes anything in Jira, Confluence, Jama or Genesys.
  Write capability is a later, deliberate decision.
- **No persisted link store.** Phase 4's cross-system linking queries each connector's native
  cross-reference fields live, on every call. A persisted/indexed link graph — which is what would
  make reverse lookups and whole-thread traversal fast — is a **future enhancement, not part of
  this pass**.
- **No backend integration.** Making the RadiaAI backend an MCP client of this server is a separate
  task.

## Tools

All read-only, all annotated `readOnlyHint: true`.

| Tool                   | Arguments                                                        | Returns                       |
| ---------------------- | ---------------------------------------------------------------- | ----------------------------- |
| `jama_get_item`        | `item_id` (required)                                             | Full item + custom fields     |
| `jama_search`          | `query`, `project_id`, `item_type_id`, `start_at`, `max_results` | Summaries + total             |
| `jama_get_children`    | `item_id` (required), `start_at`, `max_results`                  | Direct children + total       |
| `jira_get_issue`       | `issue_key` (required)                                           | Full issue + issue links      |
| `jira_search`          | `jql` (required), `next_page_token`, `max_results`               | Summaries + page token        |
| `confluence_get_page`  | `page_id` (required)                                             | Page + body as text           |
| `confluence_search`    | `query`, `space_key`, `content_type`, `cql`, `start`, `limit`    | Hits + total                  |
| `list_related_items`   | `system`, `item_id` (required), `include_text_references`        | Related items + notes         |

**Jama.** `jama_search` maps to `/abstractitems`; `query` becomes its `contains` parameter. Jama
caps page size at 50, enforced in the schema and clamped again in the connector. Descriptions
arrive as HTML and are flattened to text.

`fields` carries the item type's **custom fields**. `name`, `description` and `status` are
deliberately omitted from it because each is already returned as its own attribute — Jama repeats
the description there as raw HTML, which measured **~75% of a single item's payload** on a real
instance (111 KB → 27 KB for one requirement). Nothing is lost: the flattened `description` holds
the same text, and the linking layer scans that flattened copy, so cross-reference discovery is
unaffected.

`jama_get_children` maps to `/items/{id}/children` and returns the **containment hierarchy** — the
items nested inside a folder or set in the document tree. This is a different axis from
`list_related_items`, which walks **traceability** (upstream/downstream). Keeping them as separate
tools is deliberate: "what is filed under this" and "what derives from this" are different
questions, and one tool answering both makes the model's choice ambiguous. It returns one level
and one page per call, so a single tool call cannot fan out into an unbounded crawl; recurse by
calling it again with a child's id.

**Jira.** Uses the Cloud platform API v3.

- Search goes to `/rest/api/3/search/jql`. The older `/rest/api/3/search` was deprecated in 2024.
  That endpoint is **token-paginated and returns no total count** — hence `next_page_token` and
  `is_last` on the result, and no `total` field. Page by feeding the token back in.
- `/search/jql` returns only `id` and `key` unless `fields` is sent, which is an easy way to get
  mysteriously empty issues. The connector always sends an explicit field list.
- Descriptions are Atlassian Document Format (ADF) JSON, not text, and are flattened by
  `connectors/text.py`.
- `issuelinks` are flattened into a single `links` list with the direction and the phrasing as
  read *from this issue* — this is the native cross-reference Phase 4 will build on.

**Confluence.** Deliberately spans two API versions, because neither covers both operations:

- `confluence_get_page` uses **v2** (`/wiki/api/v2/pages/{id}?body-format=storage`). Note the
  parameter: the v1 idiom `expand=body.storage` is silently ignored by v2 and returns an empty
  body.
- `confluence_search` uses **v1** (`/wiki/rest/api/search?cql=...`). CQL search has no v2
  equivalent yet.
- `query`/`space_key`/`content_type` are composed into CQL with quotes and backslashes escaped, so
  free text cannot alter the query's meaning. Pass `cql` directly for anything that cannot express.

## Errors

Tool failures carry the **remote API's own wording**, not just a status code. A model is shown, for
example:

```
[jira] The Jira API returned an error response. operation=rest/api/3/search/jql status=400
jira said: "Unbounded JQL queries are not allowed here. Please add a search restriction to your query."
```

That trailing sentence is the only actionable part — `status=400` alone tells a model nothing about
what to change, so it cannot retry correctly. `extract_remote_message()` in
[`connectors/errors.py`](mcp_radia/connectors/errors.py) pulls the wording out of the shapes these
APIs actually use (Atlassian's `errorMessages`/`errors`, Confluence v2's list of error objects,
Jama's `meta.message`, and the OAuth `error_description` convention).

It is deliberately conservative: HTML error pages are ignored rather than dumped into the model's
context, repeated wording is de-duplicated, and anything long is truncated to 400 characters.

## Cross-system linking

`list_related_items(system, item_id)` traces one item to everything related to it. It queries the
connectors **live on every call — there is no link datastore.** The answer is therefore always
current and nothing has to be kept in sync; the cost is that one call fans out to several API
requests.

**Native cross-references** (always on) — what each system records as first-class data:

| System     | Source                                          | `relation` values            |
| ---------- | ----------------------------------------------- | ---------------------------- |
| Jira       | `issuelinks` + parent                           | `blocks`, `relates to`, `parent` … |
| Jama       | `/items/{id}/upstreamrelated` + `downstreamrelated` | `upstream`, `downstream` |
| Confluence | `<ri:page>` and `<a href>` links in the page body | `links-to`                 |
| GENESYS    | *not implemented* — returns a note              | —                            |

**Text references** (`include_text_references=true`, **off by default**). The interesting hops in
a digital thread often aren't formal links at all — someone types "traced to BMS-451" into a Jama
custom field, or names `SRS-42` in a Confluence page. When enabled, the item's text (including
Jama custom fields) is scanned for key-shaped identifiers, which are then resolved against Jira
and Jama.

This is a **heuristic**, so:

- Results are tagged `discovered_via="text"`; native links are `"native"`. You can always tell
  them apart.
- A key that resolves to nothing is returned as `system="unresolved"` rather than dropped — a
  reference you can't resolve is still a lead.
- Standards that look like keys (`ISO-26262`, `UTF-8`, `DO-178`) are filtered out.
- Lookups are capped at 10 per call, and the cap is reported in `notes`.

**Always read `notes`.** It is where the tool admits what limited the answer: a connector that
isn't configured, GENESYS being unimplemented, a truncated scan, or the fact that Confluence can
only report *outbound* links. An unconfigured system is reported there rather than silently
looking like "nothing related".

### Not in this pass

**A persisted link store is a future enhancement, not part of this work.** Querying live means
reverse lookups are limited to whatever each system indexes — Confluence, for instance, has no
supported "what links to this page" query, so inbound references are invisible. A persisted,
periodically-refreshed link graph is what would make reverse lookups and whole-thread traversal
possible and fast. That is a deliberate next step, not an oversight.

## Notes on the SDK

Built against **MCP Python SDK 2.x**, where `FastMCP` was renamed `MCPServer` and several APIs
became `snake_case` (`InitializeResult.server_info`) or async (`MCPServer.list_tools()`). Examples
written for `mcp<2` will not run unmodified.
