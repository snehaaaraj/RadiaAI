"""Structured logging configuration using structlog.

Mirrors the RadiaAI backend's logging setup (ISO timestamps, level, logger name,
contextvar merging; pretty console locally, JSON elsewhere) with one deliberate
difference: **every log record goes to stderr, never stdout.**

Under the MCP stdio transport, stdout *is* the JSON-RPC channel. A single log
line written there corrupts the protocol stream and the client drops the
connection, so stdout is off-limits for anything but protocol frames.
"""

import logging
import sys
from typing import cast

import structlog

from mcp_radia.config import ServerSettings


def configure_logging(settings: ServerSettings) -> None:
    """Configure structlog. Safe to call once at startup; re-calling resets handlers."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.environment in ("local", "development"):
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # stderr, not stdout - see the module docstring.
    root_handler = logging.StreamHandler(sys.stderr)
    root_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(root_handler)
    root_logger.setLevel(log_level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given module name."""
    return cast("structlog.stdlib.BoundLogger", structlog.get_logger(name))
