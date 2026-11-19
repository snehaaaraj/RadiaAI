# Radia MCP for VS Code

Connect GitHub Copilot to your own Jama Connect account without keeping a RadiaAI
repository checkout or running its web backend. This extension includes the
Jama-only MCP server source and a dependency lock. It does not include credentials.

## Install

1. Install [UV](https://docs.astral.sh/uv/getting-started/installation/) once using
   your IT-approved method. For Windows with WinGet, use
   `winget install --id astral-sh.uv --exact`. On macOS with Homebrew, use
   `brew install uv`. Restart VS Code after installation.
2. In local desktop VS Code 1.101 or newer, open Extensions and choose **... >
   Install from VSIX...**. Select `radia-jama-vscode-0.1.0.vsix`.
3. Open a trusted local folder. Run **Radia MCP: Connect or Update Account**
   from the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`).
4. Enter your HTTPS Jama instance root (e.g. `https://yourorg.jamacloud.com`),
   personal OAuth client ID and personal client secret. These are API
   credentials, not your email/password; ask your Jama administrator if needed.
5. Run **MCP: List Servers**, find **Radia MCP**, and start it. Review and approve
   the trust prompt. The first launch needs internet access to download Python
   3.13 and locked dependencies through UV. You do not need to install Python.
6. In GitHub Copilot Chat, select **Agent**, enable Radia MCP's tools if needed,
   and ask: **"Use Radia MCP to list the projects I can access."**

VS Code's MCP provider API registers the server; no hand-edited MCP configuration
is needed. Current Copilot sessions can receive eligible editor-provided server
definitions. If you have an older session open, restart it after setup. Organization
policy must permit MCP and sideloaded extensions. This is a desktop extension,
not vscode.dev, a remote/cloud-agent integration, or a standalone Copilot CLI plugin.
If you already configured another Radia MCP, disable one to avoid duplicate tools.

If UV is not found, set **Radia MCP: UV Path** to its executable's absolute path,
then rerun setup. The extension also checks UV's usual `~/.local/bin` location.
Do not put credentials in this setting.

## Capabilities

- Read accessible projects, search items, read full item content and custom fields.
- Read children; call the children tool on each child for grandchildren.
- Read upstream/downstream traceability with `jama_get_relationships`, paging
  each requested direction using `next_start_at` until null. These are one-hop
  related items, not relationship type/ID records.
- Prepare and explicitly confirm changes to existing fields, including Description.
  Keep tool approval enabled for `jama_confirm_field_update`. Inspect the complete
  before/after preview and approve in a later interaction before confirming.

No standards/RAG, item creation/deletion, Jira, Confluence, Violet or GENESYS
tools are registered by this extension. Jama still enforces account permissions.
Never use an API credential belonging to someone else.

## Credentials and local data

The setup command stores the connection in **VS Code SecretStorage**, not
settings, a workspace file, a bundled `.env`, or chat. Both credential inputs are
masked. Configuration is saved only after all three steps are completed.
The provider reads the saved connection noninteractively and passes credentials
to the MCP process via its environment, never command-line arguments. VS Code,
the connected Copilot runtime and local processes with sufficient access must
be trusted; secure storage does not make process environment credentials invisible.

The runtime environment is kept in VS Code's extension global-storage directory,
outside both this extension and your project. Python/UV also use their usual
download caches. UV and first-run package installation need internet access.
Your computer must reach Jama; use your company VPN when required. TLS verification
is enabled. No shared RadiaAI service token or Azure credential is required.

To rotate credentials, stop the server with **MCP: List Servers**, run
**Radia MCP: Connect or Update Account**, then start the server again. Setup does
not validate credentials against Jama; the read-only project-list request does.
Previews expire in 10 minutes and become invalid after a server restart.

To disconnect, stop the server, then run **Radia MCP: Remove Saved Account**.
Deleting stored credentials or uninstalling is not token revocation: stop any
running server and revoke credentials in Jama if required. The extension does
not change MCP tool auto-approval or organization policies.

## Troubleshooting

- **No server listed:** run setup in a trusted local folder; check extension and
  MCP organization policies. Stop/disable any other Radia configuration.
- **UV missing:** install it, restart VS Code, or configure its absolute path.
- **Startup fails:** use the server's output from MCP controls; check download,
  proxy, certificate and VPN restrictions with IT. Never send secrets in logs.
- **Authentication or permissions fail:** correct credentials through setup and
  restart. Permissions are controlled in Jama, not by this extension.
- **Uncertain write outcome:** check the Jama item; do not blindly retry.

## Maintainer build

In this directory with Node.js 22+:

```text
npm ci
npm test
npm run package
```

The VSIX is written to `../dist/radia-jama-vscode-0.1.0.vsix`. Prepublish stages
only runtime Python source, the launcher, `pyproject.toml` and `uv.lock`, then
compiles this extension. The VSIX excludes local `.env`, virtualenvs, development
dependencies and tests. Do not copy the repository into a VSIX manually.
Keep this package's version aligned with the MCP desktop manifest.

This is a privately sideloaded, unpublished extension, with no automatic update
service. Share through your organization's trusted channel and install updated
VSIX files manually. Pilot on Windows/macOS and a non-production Jama project.
Protocol/unit tests do not verify VS Code's actual UI or a live Jama tenant.
