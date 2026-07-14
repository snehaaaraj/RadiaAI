"""
Request ID management using Python contextvars.

A unique request ID is generated per HTTP request (or accepted from the
X-Request-ID header if the caller provides one). It is stored in a contextvar
so that structlog can automatically include it in every log line produced
during that request's lifecycle — without passing it as a function argument.
"""

import uuid
from contextvars import ContextVar

# Module-level context variable; default is empty string so logs before a
# request starts don't fail.
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def set_request_id(request_id: str) -> None:
    """Set the current request ID in the context variable."""
    _request_id_ctx.set(request_id)


def get_request_id() -> str:
    """Return the current request ID, or a new UUID if none is set."""
    return _request_id_ctx.get() or str(uuid.uuid4())


def generate_request_id() -> str:
    """Generate a new UUID4 request ID."""
    return str(uuid.uuid4())
