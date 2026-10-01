"""Exception hierarchy shared by every connector.

The tool layer catches :class:`ConnectorError` and turns it into an MCP
``ToolError``, so a connector never needs to know anything about MCP. Each
subclass corresponds to a failure the caller can act on differently:

  - :class:`ConnectorNotConfiguredError` - operator has not supplied credentials.
  - :class:`ConnectorAuthError`          - credentials present but rejected.
  - :class:`ItemNotFoundError`           - the request was fine, the thing is not there.
  - :class:`ConnectorServiceError`       - anything else (5xx, timeouts, bad payloads).
  - :class:`ConnectorNotImplementedError` - the connector is a placeholder.
"""

import json
from typing import Any

#: Key under which a connector stores the remote API's own error wording, so
#: :meth:`ConnectorError.__str__` can surface it to the model.
REMOTE_MESSAGE_KEY = "remote_message"

#: Remote messages are truncated to this many characters. Long enough for a
#: real remediation hint, short enough that an HTML error page cannot flood the
#: model's context.
_MAX_REMOTE_MESSAGE = 400


def _clean(text: str) -> str:
    return " ".join(text.split())


def _truncate(text: str) -> str:
    text = _clean(text)
    if len(text) <= _MAX_REMOTE_MESSAGE:
        return text
    return text[: _MAX_REMOTE_MESSAGE - 1].rstrip() + "…"


def _candidates(payload: object) -> list[str]:
    """Pull human-readable strings out of a parsed JSON error body.

    Covers the shapes the connectors actually meet: Atlassian's
    ``{"errorMessages": [...], "errors": {...}}``, Jama's
    ``{"meta": {"message": ...}}``, and the ``message`` / ``error`` /
    ``error_description`` conventions used by OAuth endpoints.
    """
    if isinstance(payload, str):
        return [payload]
    if not isinstance(payload, dict):
        return []

    found: list[str] = []

    messages = payload.get("errorMessages")
    if isinstance(messages, list):
        found.extend(str(m) for m in messages if m)

    errors = payload.get("errors")
    if isinstance(errors, dict):
        found.extend(f"{k}: {v}" for k, v in errors.items() if v)
    elif isinstance(errors, list):
        # Confluence v2 returns a list of error objects; recurse so their
        # 'title'/'detail' wording is used rather than a raw dict repr.
        for entry in errors:
            if isinstance(entry, dict):
                found.extend(_candidates(entry))
            elif entry:
                found.append(str(entry))

    for key in ("message", "error_description", "error", "detail", "title"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            found.append(value)

    # Jama nests its wording under meta.
    meta = payload.get("meta")
    if isinstance(meta, dict):
        found.extend(_candidates(meta))

    return found


def extract_remote_message(body: str) -> str | None:
    """Return the remote API's own error wording, or ``None`` if there is none.

    The status code alone rarely says what to change - Jira answers a bare
    ``ORDER BY`` query with 400 and the words "Unbounded JQL queries are not
    allowed here", which is the only part a model can act on. Connectors feed
    the raw response body here so that wording survives into the tool error.
    """
    if not body or not body.strip():
        return None

    try:
        payload = json.loads(body)
    except ValueError:
        # Not JSON. An HTML error page is noise, so only pass through short
        # plain-text bodies, which some gateways do return.
        text = _clean(body)
        if not text or text.startswith("<") or len(text) > _MAX_REMOTE_MESSAGE:
            return None
        return text

    found = [_clean(c) for c in _candidates(payload)]
    # Deduplicate while keeping order: APIs often repeat the same wording in
    # two fields, and showing it twice wastes the model's attention.
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in found:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    if not unique:
        return None
    return _truncate(" | ".join(unique))


class ConnectorError(Exception):
    """Base class for every failure raised by a connector."""

    def __init__(
        self,
        message: str,
        *,
        system: str,
        operation: str | None = None,
        status_code: int | None = None,
        detail: dict[str, Any] | None = None,
        remote_message: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.system = system
        self.operation = operation
        self.status_code = status_code
        self.detail = dict(detail or {})
        if remote_message:
            self.detail[REMOTE_MESSAGE_KEY] = remote_message

    @property
    def remote_message(self) -> str | None:
        """What the remote API itself said, if the connector captured it."""
        value = self.detail.get(REMOTE_MESSAGE_KEY)
        return value if isinstance(value, str) and value else None

    def __str__(self) -> str:
        parts = [f"[{self.system}] {self.message}"]
        if self.operation:
            parts.append(f"operation={self.operation}")
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        # Last, and quoted, because this is the part a model can actually act
        # on - "add a search restriction" beats "status=400".
        if self.remote_message:
            parts.append(f'{self.system} said: "{self.remote_message}"')
        return " ".join(parts)


class ConnectorNotConfiguredError(ConnectorError):
    """The connector has no usable credentials, so no call was attempted."""


class ConnectorAuthError(ConnectorError):
    """The remote system rejected the supplied credentials (401/403)."""


class ItemNotFoundError(ConnectorError):
    """The requested record does not exist or is not visible to this account."""


class ConnectorServiceError(ConnectorError):
    """The remote system errored, was unreachable, or returned an unusable payload."""


class ConnectorNotImplementedError(ConnectorError):
    """The connector exists as a placeholder but has no working implementation.

    Distinct from :class:`ConnectorNotConfiguredError`: no amount of credentials
    will make this call work until the connector is built.
    """
