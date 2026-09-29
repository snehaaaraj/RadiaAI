"""Exception hierarchy shared by every connector.

The tool layer catches :class:`ConnectorError` and turns it into an MCP
``ToolError``, so a connector never needs to know anything about MCP. Each
subclass corresponds to a failure the caller can act on differently:

  - :class:`ConnectorNotConfiguredError` - operator has not supplied credentials.
  - :class:`ConnectorAuthError`          - credentials present but rejected.
  - :class:`ItemNotFoundError`           - the request was fine, the thing is not there.
  - :class:`ConnectorServiceError`       - anything else (5xx, timeouts, bad payloads).
"""

from typing import Any


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
    ) -> None:
        super().__init__(message)
        self.message = message
        self.system = system
        self.operation = operation
        self.status_code = status_code
        self.detail = detail or {}

    def __str__(self) -> str:
        parts = [f"[{self.system}] {self.message}"]
        if self.operation:
            parts.append(f"operation={self.operation}")
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        return " ".join(parts)


class ConnectorNotConfiguredError(ConnectorError):
    """The connector has no usable credentials, so no call was attempted."""


class ConnectorAuthError(ConnectorError):
    """The remote system rejected the supplied credentials (401/403)."""


class ItemNotFoundError(ConnectorError):
    """The requested record does not exist or is not visible to this account."""


class ConnectorServiceError(ConnectorError):
    """The remote system errored, was unreachable, or returned an unusable payload."""
