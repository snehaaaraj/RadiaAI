"""
Structured logging configuration using structlog.

Every log record automatically includes:
  - timestamp (ISO 8601)
  - log level
  - logger name
  - request_id (injected via context var, see utils/request_id.py)

Call configure_logging() once at application startup.
"""

import logging
import sys
from typing import cast

import structlog

from app.core.config import AppSettings


def configure_logging(settings: AppSettings) -> None:
    """
    Configure structlog for structured JSON output in production and
    pretty-printed console output in local/development environments.
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure the standard library logging to feed into structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Processors applied to every log record
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,  # inject request_id etc.
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.environment in ("local", "development"):
        # Human-friendly coloured output during local development. ConsoleRenderer
        # already pretty-prints exc_info itself, so no extra processor is needed.
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(colors=True)
        final_processors: list[structlog.types.Processor] = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ]
    else:
        # Machine-readable JSON for log aggregation (e.g. Azure Monitor, Vercel logs).
        # Unlike ConsoleRenderer, JSONRenderer does not know how to turn exc_info=True
        # (or a raised exception) into readable text on its own - without
        # format_exc_info here, a logger.warning(..., exc_info=True) call renders as
        # the literal, useless field {"exc_info": true} instead of the traceback,
        # which is exactly what made a real production failure undiagnosable.
        renderer = structlog.processors.JSONRenderer()
        final_processors = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            renderer,
        ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Attach structlog formatter to the root stdlib handler
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=final_processors,
    )

    root_handler = logging.StreamHandler(sys.stdout)
    root_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Remove any existing handlers added by basicConfig above
    root_logger.handlers.clear()
    root_logger.addHandler(root_handler)
    root_logger.setLevel(log_level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given module name."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
