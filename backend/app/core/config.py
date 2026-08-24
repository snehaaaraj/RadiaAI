"""
Application configuration loaded from environment variables via Pydantic Settings.

All Azure endpoints, keys, and deployment names must be provided through the
environment (or a .env file during local development). Nothing is hardcoded here.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env location: check backend/.env first, then project root .env
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent  # RadiaAi-2.0/
_ENV_FILE = (
    str(_BACKEND_DIR / ".env") if (_BACKEND_DIR / ".env").exists() else str(_PROJECT_ROOT / ".env")
)


def _azure_openai_settings_factory() -> "AzureOpenAISettings":
    return cast(AzureOpenAISettings, cast(Any, AzureOpenAISettings)())


def _azure_search_settings_factory() -> "AzureSearchSettings":
    return cast(AzureSearchSettings, cast(Any, AzureSearchSettings)())


def _azure_blob_settings_factory() -> "AzureBlobSettings":
    return cast(AzureBlobSettings, cast(Any, AzureBlobSettings)())


def _entra_id_settings_factory() -> "EntraIDSettings":
    return cast(EntraIDSettings, cast(Any, EntraIDSettings)())


def _sharepoint_settings_factory() -> "SharePointSettings":
    return cast(SharePointSettings, cast(Any, SharePointSettings)())


class AzureOpenAISettings(BaseSettings):
    """Azure OpenAI service configuration."""

    model_config = SettingsConfigDict(
        env_prefix="AZURE_OPENAI_", env_file=_ENV_FILE, extra="ignore"
    )

    endpoint: AnyHttpUrl = Field(..., description="Azure OpenAI resource endpoint")
    api_key: str = Field(..., description="Azure OpenAI API key")
    api_version: str = Field(default="2024-10-21", description="API version")
    chat_deployment: str = Field(..., description="Chat completion deployment name (e.g. gpt-4o)")
    embedding_deployment: str = Field(
        ..., description="Embedding deployment name (e.g. text-embedding-3-large)"
    )
    embedding_dimensions: int = Field(default=3072, description="Embedding vector dimensions")
    max_tokens: int = Field(default=4096, description="Max tokens for chat completions")
    temperature: float = Field(default=0.0, description="Sampling temperature (0 = deterministic)")


class AzureSearchSettings(BaseSettings):
    """Azure AI Search service configuration."""

    model_config = SettingsConfigDict(
        env_prefix="AZURE_SEARCH_", env_file=_ENV_FILE, extra="ignore"
    )

    endpoint: AnyHttpUrl = Field(..., description="Azure AI Search endpoint")
    api_key: str = Field(..., description="Azure AI Search admin key")
    index_name: str = Field(default="radia-documents", description="Search index name")
    semantic_config_name: str = Field(
        default="radia-semantic-config", description="Semantic configuration name"
    )


class AzureBlobSettings(BaseSettings):
    """Azure Blob Storage configuration."""

    model_config = SettingsConfigDict(env_prefix="AZURE_BLOB_", env_file=_ENV_FILE, extra="ignore")

    connection_string: str = Field(..., description="Blob Storage connection string")
    container_name: str = Field(
        default="radia-documents", description="Blob container for uploaded documents"
    )


class SharePointSettings(BaseSettings):
    """SharePoint / Microsoft Graph API settings for standards document library."""

    model_config = SettingsConfigDict(env_prefix="SHAREPOINT_", env_file=_ENV_FILE, extra="ignore")

    tenant_id: str = Field(
        default="", description="Azure AD tenant ID (can share with ENTRA_TENANT_ID)"
    )
    client_id: str = Field(default="", description="App registration client ID with Sites.Read.All")
    client_secret: str = Field(default="", description="App registration client secret")
    site_url: str = Field(
        default="https://radia99.sharepoint.com/sites/sysengint",
        description="SharePoint site root URL",
    )
    drive_name: str = Field(
        default="Requirements Management",
        description="SharePoint document library (drive) name",
    )
    standards_folder: str = Field(
        default="0. Reference Material/AI Reference Material",
        description="Folder path within the drive containing standard documents",
    )
    cache_ttl_seconds: int = Field(
        default=300,
        description="How long to cache the file listing before re-fetching (seconds)",
    )

    @property
    def is_configured(self) -> bool:
        """True only when all credentials and site URL are set."""
        return bool(self.tenant_id and self.client_id and self.client_secret and self.site_url)


class EntraIDSettings(BaseSettings):
    """Microsoft Entra ID (Azure AD) configuration for authentication."""

    model_config = SettingsConfigDict(env_prefix="ENTRA_", env_file=_ENV_FILE, extra="ignore")

    tenant_id: str = Field(default="", description="Azure AD tenant ID")
    client_id: str = Field(default="", description="Application (client) ID")
    client_secret: str = Field(default="", description="Client secret")
    audience: str = Field(default="", description="Token audience (api://client_id)")

    @property
    def is_configured(self) -> bool:
        """Returns True only when all Entra fields are populated."""
        return bool(self.tenant_id and self.client_id and self.audience)


class AppSettings(BaseSettings):
    """Top-level application settings that aggregate all sub-settings."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = Field(default="Radia AI", description="Human-readable application name")
    app_version: str = Field(default="0.1.0")
    environment: Literal["local", "development", "staging", "production"] = Field(
        default="local", description="Deployment environment"
    )
    debug: bool = Field(default=False, description="Enable debug mode (never True in production)")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")

    # --- API ---
    api_prefix: str = Field(default="/api/v1")
    allowed_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="CORS allowed origins",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: str | list[str]) -> list[str]:
        """Parse ALLOWED_ORIGINS from JSON string or list."""
        if isinstance(value, str):
            import json

            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                # Fall back to comma-separated string
                return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value if isinstance(value, list) else []

    # --- RAG ---
    retrieval_top_k: int = Field(
        default=5, ge=1, le=20, description="Number of chunks to retrieve per query"
    )
    chunk_size: int = Field(default=512, ge=128, le=4096, description="Token size per chunk")
    chunk_overlap: int = Field(default=64, ge=0, le=512, description="Token overlap between chunks")

    # --- Sub-settings (populated from prefixed env vars) ---
    azure_openai: AzureOpenAISettings = Field(default_factory=_azure_openai_settings_factory)
    azure_search: AzureSearchSettings = Field(default_factory=_azure_search_settings_factory)
    azure_blob: AzureBlobSettings = Field(default_factory=_azure_blob_settings_factory)
    entra: EntraIDSettings = Field(default_factory=_entra_id_settings_factory)
    sharepoint: SharePointSettings = Field(default_factory=_sharepoint_settings_factory)

    @field_validator("debug")
    @classmethod
    def no_debug_in_production(cls, value: bool, info: object) -> bool:
        """Prevent debug mode from being enabled in production environments."""
        # We check the raw values dict since environment may not be validated yet
        data = getattr(info, "data", {})
        if data.get("environment") == "production" and value:
            raise ValueError("debug=True is not allowed in the production environment")
        return value


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """
    Return a cached singleton of AppSettings.

    Using lru_cache means the .env file is read exactly once at startup,
    and the same Settings object is reused for every dependency injection.
    Call get_settings.cache_clear() in tests to reset between test cases.
    """
    return AppSettings()
