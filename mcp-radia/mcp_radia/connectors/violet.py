"""MCP client for Violet's remote Streamable HTTP server."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal, Protocol

import anyio
import httpx2
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp_radia.config import ENV_FILE
from mcp_radia.connectors.errors import (
    ConnectorAuthError,
    ConnectorNotConfiguredError,
    ConnectorServiceError,
)
from mcp_radia.logging import get_logger

logger = get_logger(__name__)

SYSTEM = "violet"
_MAX_RETRY_ATTEMPTS = 3
_MAX_RETRY_DELAY_SECONDS = 2.0


class VioletSettings(BaseSettings):
    """Violet MCP settings. The initial integration supports API-key auth only."""

    model_config = SettingsConfigDict(env_prefix="VIOLET_", env_file=ENV_FILE, extra="ignore")

    server_url: str = Field(
        default="https://mcp.violetlabs.com/mcp",
        description="Remote MCP endpoint; use https://mcp.violetgov.com/mcp for VioletGov.",
    )
    auth_mode: Literal["apikey"] = Field(
        default="apikey",
        description="Violet authentication mode. OAuth is deferred pending provider details.",
    )
    api_key: str = Field(default="", repr=False, description="Violet user API key.")
    timeout_seconds: float = Field(default=20.0, gt=0, description="Per-call timeout.")

    @property
    def is_configured(self) -> bool:
        """Whether the remote endpoint has the API key required for calls."""
        return bool(self.server_url.strip() and self.api_key.strip())


class VioletToolTransport(Protocol):
    """Transport seam used by the client and its offline tests."""

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class VioletMCPClient:
    """Owns one reusable MCP session to Violet for the lifetime of the Radia server."""

    def __init__(
        self,
        settings: VioletSettings,
        *,
        transport: VioletToolTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._session: ClientSession | None = None
        self._initialized = False
        self._call_lock = asyncio.Lock()
        self._last_status_code: int | None = None
        # The SDK's transport debug log includes full JSON-RPC messages.
        logging.getLogger("mcp.client.streamable_http").setLevel(logging.INFO)

    @property
    def is_configured(self) -> bool:
        return self._settings.is_configured

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        """Keep the MCP session alive under the server's own lifespan."""
        if self._transport is not None or not self.is_configured:
            yield
            return

        timeout = httpx2.Timeout(self._settings.timeout_seconds)
        async with (
            httpx2.AsyncClient(
                headers={"X-API-Key": self._settings.api_key},
                timeout=timeout,
            ) as http_client,
            streamable_http_client(
                self._settings.server_url,
                http_client=http_client,
            ) as (read_stream, write_stream),
        ):
            http_client.event_hooks["response"].append(self._record_response)
            async with ClientSession(read_stream, write_stream) as session:
                self._session = session
                try:
                    yield
                finally:
                    self._session = None
                    self._initialized = False

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call one remote Violet tool, preserving its structured result."""
        if not self.is_configured:
            raise ConnectorNotConfiguredError(
                "Violet MCP is not configured. Set VIOLET_API_KEY on the MCP service.",
                system=SYSTEM,
                operation=name,
            )

        if self._transport is not None:
            try:
                with anyio.fail_after(self._settings.timeout_seconds):
                    return await self._transport.call_tool(name, arguments)
            except TimeoutError as exc:
                raise ConnectorServiceError(
                    "Violet MCP timed out. Try again or narrow the request.",
                    system=SYSTEM,
                    operation=name,
                ) from exc
            except httpx2.TimeoutException as exc:
                raise ConnectorServiceError(
                    "Violet MCP timed out. Try again or narrow the request.",
                    system=SYSTEM,
                    operation=name,
                ) from exc
            except httpx2.HTTPError as exc:
                raise ConnectorServiceError(
                    "Could not reach Violet MCP. Try again later.",
                    system=SYSTEM,
                    operation=name,
                ) from exc

        async with self._call_lock:
            session = self._session
            if session is None:
                raise ConnectorServiceError(
                    "The Violet MCP session is not available. Retry the request.",
                    system=SYSTEM,
                    operation=name,
                )
            try:
                with anyio.fail_after(self._settings.timeout_seconds):
                    return await self._call_with_retries(session, name, arguments)
            except TimeoutError as exc:
                raise ConnectorServiceError(
                    "Violet MCP timed out. Try again or narrow the request.",
                    system=SYSTEM,
                    operation=name,
                ) from exc
            except httpx2.TimeoutException as exc:
                raise ConnectorServiceError(
                    "Violet MCP timed out. Try again or narrow the request.",
                    system=SYSTEM,
                    operation=name,
                ) from exc
            except httpx2.HTTPError as exc:
                self._raise_for_auth_status(name)
                raise ConnectorServiceError(
                    "Could not reach Violet MCP. Try again later.",
                    system=SYSTEM,
                    operation=name,
                ) from exc
            except MCPError as exc:
                self._raise_for_auth_status(name)
                raise ConnectorServiceError(
                    "Violet MCP rejected the request. Check the tool arguments and try again.",
                    system=SYSTEM,
                    operation=name,
                ) from exc

    async def _call_with_retries(
        self,
        session: ClientSession,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        for attempt in range(1, _MAX_RETRY_ATTEMPTS + 1):
            self._last_status_code = None
            try:
                if not self._initialized:
                    await session.initialize()
                    self._initialized = True
                result = await session.call_tool(name, arguments)
            except MCPError:
                if self._is_auth_failure():
                    self._raise_for_auth_status(name)
                if self._last_status_code == 429 and attempt < _MAX_RETRY_ATTEMPTS:
                    delay = min(0.5 * (2 ** (attempt - 1)), _MAX_RETRY_DELAY_SECONDS)
                    logger.warning(
                        "violet_rate_limited_retry",
                        tool=name,
                        attempt=attempt,
                        delay_seconds=delay,
                    )
                    await anyio.sleep(delay)
                    continue
                raise

            if self._is_auth_failure():
                self._raise_for_auth_status(name)
            if self._last_status_code == 429 and attempt < _MAX_RETRY_ATTEMPTS:
                delay = min(0.5 * (2 ** (attempt - 1)), _MAX_RETRY_DELAY_SECONDS)
                logger.warning(
                    "violet_rate_limited_retry",
                    tool=name,
                    attempt=attempt,
                    delay_seconds=delay,
                )
                await anyio.sleep(delay)
                continue
            if result.is_error:
                raise ConnectorServiceError(
                    "Violet could not complete the read request.",
                    system=SYSTEM,
                    operation=name,
                    status_code=self._last_status_code,
                )
            structured_content = result.structured_content
            if isinstance(structured_content, dict):
                return {str(key): value for key, value in structured_content.items()}
            return {
                "content": [
                    block.model_dump(mode="json", by_alias=True) for block in result.content
                ]
            }

        raise ConnectorServiceError(
            "Violet remained rate limited after bounded retries.",
            system=SYSTEM,
            operation=name,
            status_code=429,
        )

    async def _record_response(self, response: httpx2.Response) -> None:
        self._last_status_code = response.status_code

    def _is_auth_failure(self) -> bool:
        return self._last_status_code in {401, 403}

    def _raise_for_auth_status(self, operation: str) -> None:
        if self._is_auth_failure():
            raise ConnectorAuthError(
                "Violet rejected the API key or denied access. Check the key and workspace "
                "permissions in Violet.",
                system=SYSTEM,
                operation=operation,
                status_code=self._last_status_code,
            )
