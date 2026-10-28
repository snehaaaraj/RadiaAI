"""Command-line entrypoint for the RadiaAI MCP server.

Two transports are supported from one tool registry:

  ``mcp-radia stdio``  - MCP over stdin/stdout (the default). This is what
                         Claude Desktop, the MCP Inspector and other local
                         clients launch as a subprocess.
  ``mcp-radia http``   - MCP over Streamable HTTP, for running the server as a
                         deployed network service.
"""

import argparse
import sys
from collections.abc import Sequence

from mcp_radia import __version__
from mcp_radia.asgi import build_http_app
from mcp_radia.config import ServerSettings, get_settings
from mcp_radia.logging import configure_logging, get_logger
from mcp_radia.server import build_server

logger = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``mcp-radia`` command."""
    parser = argparse.ArgumentParser(
        prog="mcp-radia",
        description="RadiaAI digital-thread MCP server (read-only).",
    )
    parser.add_argument("--version", action="version", version=f"mcp-radia {__version__}")

    subparsers = parser.add_subparsers(dest="transport")
    subparsers.add_parser("stdio", help="Serve MCP over stdin/stdout (default).")

    http = subparsers.add_parser("http", help="Serve MCP over Streamable HTTP.")
    http.add_argument("--host", default=None, help="Bind address (overrides MCP_RADIA_HOST).")
    http.add_argument(
        "--port", type=int, default=None, help="Bind port (overrides MCP_RADIA_PORT)."
    )

    return parser


def _resolve_settings(args: argparse.Namespace) -> ServerSettings:
    """Apply CLI overrides on top of the environment-derived settings."""
    settings = get_settings()
    overrides: dict[str, object] = {}
    if getattr(args, "host", None) is not None:
        overrides["host"] = args.host
    if getattr(args, "port", None) is not None:
        overrides["port"] = args.port
    if not overrides:
        return settings
    # Re-validate rather than mutate, so a bad --port fails the same way a bad
    # MCP_RADIA_PORT does instead of slipping through as an unchecked attribute.
    return ServerSettings.model_validate({**settings.model_dump(), **overrides})


def main(argv: Sequence[str] | None = None) -> int:
    """Run the server. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    transport: str = args.transport or "stdio"

    settings = _resolve_settings(args)
    configure_logging(settings)
    server = build_server(settings)

    if transport == "http":
        import uvicorn

        try:
            app = build_http_app(settings, stateless=False)
        except ValueError as exc:
            logger.error("mcp_server_misconfigured", error=str(exc))
            print(f"error: {exc}", file=sys.stderr)
            return 1

        logger.info("mcp_server_starting", transport="streamable-http", url=settings.http_url)
        uvicorn_config = uvicorn.Config(
            app, host=settings.host, port=settings.port, log_level=settings.log_level.lower()
        )
        uvicorn.Server(uvicorn_config).run()
    else:
        # No startup log before the handshake: the client is already listening
        # on stdout and stderr noise is the only thing that is safe here.
        logger.info("mcp_server_starting", transport="stdio")
        server.run("stdio")

    return 0


def run() -> None:
    """Console-script shim: turn ``main``'s exit code into a process exit."""
    raise SystemExit(main())
