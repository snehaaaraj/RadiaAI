# mcp-radia

A standalone [Model Context Protocol](https://modelcontextprotocol.io) server that will expose
RadiaAI's engineering systems of record — **Jama, Jira, Confluence and Genesys** — through one
read-only MCP surface, as a digital-thread integration layer.

> **Status: Phase 0 (scaffold).** The server starts, completes an MCP handshake over either
> transport, and exposes **zero tools**. Connectors land in later phases — see
> [Roadmap](#roadmap).

## Relationship to the rest of this repo

`mcp-radia/` is deliberately **independent** of `backend/` and `frontend/`:

- Its own `pyproject.toml`, `.env`, tests and virtualenv.
- It **never imports** from `app` or `radia_ai`, and nothing in `backend/` imports from it.
- It reads only `mcp-radia/.env` — never `backend/.env` or the repo-root `.env`.

The backend's existing Jama connector was read for inspiration, but the connector here is a fresh
implementation. Wiring the RadiaAI backend up as a *client* of this server is explicitly **not**
part of this work.

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

Phase 0 needs **no credentials** — it talks to no external system. Every setting has a working
default, so the server runs against an empty `.env`. All settings are prefixed `MCP_RADIA_`:

| Variable                | Default     | Purpose                                        |
| ----------------------- | ----------- | ---------------------------------------------- |
| `MCP_RADIA_ENVIRONMENT` | `local`     | `local`/`development` ⇒ console logs, else JSON |
| `MCP_RADIA_LOG_LEVEL`   | `INFO`      | `DEBUG`…`CRITICAL`                             |
| `MCP_RADIA_HOST`        | `127.0.0.1` | HTTP transport bind address                    |
| `MCP_RADIA_PORT`        | `8081`      | HTTP transport bind port                       |
| `MCP_RADIA_HTTP_PATH`   | `/mcp`      | Path the HTTP transport is mounted at           |

Port `8081` is the default specifically so it does not collide with the RadiaAI backend on `8000`.

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

No test in this suite touches the network. The smoke tests drive the server through a **real MCP
client session over in-memory streams**, so the handshake and `tools/list` are exercised for real
without binding a port or spawning a process. Connector tests in later phases mock HTTP at the
transport layer.

There is currently **no CI workflow** for this package — the repo's existing workflows are
path-filtered to `backend/**` and `frontend/**`, so they neither run against nor are affected by
this directory. Run the commands above locally before committing.

## Layout

```
mcp-radia/
├── mcp_radia/
│   ├── cli.py          # argparse entrypoint; stdio + http subcommands
│   ├── config.py       # pydantic-settings, MCP_RADIA_* prefix
│   ├── logging.py      # structlog -> stderr
│   ├── server.py       # build_server(): constructs the MCPServer
│   └── tools/          # single registration point for every MCP tool
└── tests/
```

The importable package is `mcp_radia` (underscore) inside the `mcp-radia` project directory, since
a hyphen is not legal in a Python package name.

`register_tools()` in [`mcp_radia/tools/__init__.py`](mcp_radia/tools/__init__.py) is the one place
that lists the server's entire surface area. Each phase adds its registration call there.

## Roadmap

| Phase | Scope                                                              | Status |
| ----- | ------------------------------------------------------------------ | ------ |
| 0     | Scaffold: server, config, logging, both transports, smoke tests     | ✅ done |
| 1     | Jama connector — `jama_get_item`, `jama_search`                     | todo   |
| 2     | Jira + Confluence — `jira_get_issue`, `jira_search`, `confluence_*` | todo   |
| 3     | Genesys — `genesys_get_record`, `genesys_search` (naming TBC)       | todo   |
| 4     | `list_related_items(system, item_id)` cross-system linking          | todo   |

### Deliberate non-goals for this pass

- **Read-only.** No tool creates, updates or deletes anything in Jira, Confluence, Jama or Genesys.
  Write capability is a later, deliberate decision.
- **No persisted link store.** Phase 4's cross-system linking queries each connector's native
  cross-reference fields live, on every call. A persisted/indexed link graph — which is what would
  make reverse lookups and whole-thread traversal fast — is a **future enhancement, not part of
  this pass**.
- **No backend integration.** Making the RadiaAI backend an MCP client of this server is a separate
  task.

## Notes on the SDK

Built against **MCP Python SDK 2.x**, where `FastMCP` was renamed `MCPServer` and several APIs
became `snake_case` (`InitializeResult.server_info`) or async (`MCPServer.list_tools()`). Examples
written for `mcp<2` will not run unmodified.
