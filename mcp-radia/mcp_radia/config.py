"""Server configuration loaded from environment variables via Pydantic Settings.

Values come from the process environment or, during local development, from
``mcp-radia/.env``. Nothing is hardcoded here and nothing is read from the
RadiaAI backend's environment - the two services are deployed separately and
must not share credentials by accident.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Deliberately *not* a walk up the tree looking for the nearest .env: that would
# silently pick up backend/.env or the repo-root .env and couple this server to
# the backend's configuration. Only the .env beside our own pyproject.toml counts.
_PROJECT_DIR = Path(__file__).resolve().parent.parent

#: The only .env this server ever reads. Connector settings classes import this
#: so every one of them loads from the same file.
ENV_FILE = str(_PROJECT_DIR / ".env")

type DeploymentEnvironment = Literal["local", "development", "test", "staging", "production"]
type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class ServerSettings(BaseSettings):
    """Runtime settings for the MCP server process itself.

    Connector credentials (Jama, Jira, Confluence, Genesys) are not here yet -
    each connector brings its own settings class as it lands in a later phase.
    """

    model_config = SettingsConfigDict(
        env_prefix="MCP_RADIA_",
        env_file=ENV_FILE,
        extra="ignore",
    )

    environment: DeploymentEnvironment = Field(
        default="local",
        description="Deployment environment; controls log rendering.",
    )
    log_level: LogLevel = Field(
        default="INFO",
        description="Minimum log level emitted by the server.",
    )
    host: str = Field(
        default="127.0.0.1",
        description="Bind address for the HTTP transport. Ignored by the stdio transport.",
    )
    port: int = Field(
        default=8081,
        ge=1,
        le=65535,
        description=(
            "Bind port for the HTTP transport. Defaults to 8081 so it does not "
            "collide with the RadiaAI backend on 8000."
        ),
    )
    http_path: str = Field(
        default="/mcp",
        description="URL path the Streamable HTTP transport is mounted at.",
    )

    @property
    def http_url(self) -> str:
        """Full URL an MCP client should point at when the HTTP transport is used."""
        return f"http://{self.host}:{self.port}{self.http_path}"


@lru_cache
def get_settings() -> ServerSettings:
    """Return the process-wide settings, parsed once."""
    return ServerSettings()
