"""Unit tests for structlog configuration (app.core.logging).

Verifies specifically that exceptions logged with exc_info=True actually
produce a readable traceback in the production JSON renderer - a real
production incident surfaced that without format_exc_info in the pipeline,
such a call renders as the useless literal {"exc_info": true} instead of the
exception text, making the real failure undiagnosable from the logs alone.
"""

from __future__ import annotations

import json
import logging

import pytest

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _restore_logging_config():
    """configure_logging() mutates global state (root logger handlers, structlog
    config); restore both after each test so this suite cannot affect others."""
    yield
    get_settings.cache_clear()
    logging.getLogger().handlers.clear()


def test_json_renderer_includes_the_real_exception_text(capsys: pytest.CaptureFixture[str]) -> None:
    settings = get_settings().model_copy(update={"environment": "production"})
    configure_logging(settings)
    logger = get_logger("test.exc_info")

    try:
        raise ValueError("a specific, identifiable failure reason")
    except ValueError:
        logger.warning("something_failed", exc_info=True)

    output = capsys.readouterr().out
    record = json.loads(output.strip().splitlines()[-1])

    assert record["event"] == "something_failed"
    # The literal, useless output this test guards against: exc_info never
    # making it past the boolean flag into actual traceback text.
    assert record.get("exc_info") is not True
    exception_text = record.get("exception", "")
    assert "ValueError" in exception_text
    assert "a specific, identifiable failure reason" in exception_text


def test_json_renderer_output_is_still_valid_json_when_there_is_no_exception(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """format_exc_info must be a no-op when there is nothing to format."""
    settings = get_settings().model_copy(update={"environment": "production"})
    configure_logging(settings)
    logger = get_logger("test.exc_info")

    logger.info("ordinary_event", some_field="value")

    output = capsys.readouterr().out
    record = json.loads(output.strip().splitlines()[-1])

    assert record["event"] == "ordinary_event"
    assert record["some_field"] == "value"
    assert "exception" not in record


def test_console_renderer_still_handles_exceptions_in_local_environment(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The dev console path renders exceptions itself; must keep working unchanged."""
    settings = get_settings().model_copy(update={"environment": "local"})
    configure_logging(settings)
    logger = get_logger("test.exc_info")

    try:
        raise RuntimeError("console path failure")
    except RuntimeError:
        logger.warning("console_event", exc_info=True)

    output = capsys.readouterr().out
    assert "RuntimeError" in output
    assert "console path failure" in output
