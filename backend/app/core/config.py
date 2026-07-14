"""
Application configuration loaded from environment variables via Pydantic Settings.

All Azure endpoints, keys, and deployment names must be provided through the
environment (or a .env file during local development). Nothing is hardcoded here.
"""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureOpenAISettings(BaseSettings):
    """Azure OpenAI service configuration."""

    model_config = SettingsConfigDict(env_prefix="AZURE_OPENAI_", extra="ignore")

    endpoint: AnyHttpUrl = Field(..., description="Azure OpenAI resource endpoint")
    api_key: str = Field(..., description="Azure OpenAI API key")
    api_version: str = Field(default="2024-08-01-preview", description="API version")
    chat_deployment: str = Field(..., description="Chat completion deployment name (e.g. gpt-4o)")
    embedding_deployment: str = Field(
        ..., description="Embedding deployment name (e.g. text-embedding-3-large)"
    )
    embedding_dimensions: int = Field(default=3072, description="Embedding vector dimensions")
    max_tokens: int = Field(default=4096, description="Max tokens for chat completions")
    temperature: float = Field(default=0.0, description="Sampling temperature (0 = deterministic)")


class AzureSearchSettings(BaseSettings):
    """Azure AI Search service configuration."""

    model_config = SettingsConfigDict(env_prefix="AZURE_SEARCH_", extra="ignore")

    endpoint: AnyHttpUrl = Field(..., description="Azure AI Search endpoint")
    api_key: str = Field(..., description="Azure AI Search admin key")
    index_name: str = Field(default="radia-documents", description="Search index name")
    semantic_config_name: str = Field(
        default="radia-semantic-config", description="Semantic configuration name"
    )


class AzureBlobSettings(BaseSettings):
    """Azure Blob Storage configuration."""

    model_config = SettingsConfigDict(env_prefix="AZURE_BLOB_", extra="ignore")

    connection_string: str = Field(..., description="Blob Storage connection string")
    container_name: str = Field(
        default="radia-documents", description="Blob container for uploaded documents"
    )


class EntraIDSettings(BaseSettings):
    """Microsoft Entra ID (Azure AD) configuration for authentication."""

    model_config = SettingsConfigDict(env_prefix="ENTRA_", extra="ignore")

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
        env_file=".env",
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
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )

    # --- API ---
    api_prefix: str = Field(default="/api/v1")
    allowed_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="CORS allowed origins",
    )

    # --- RAG ---
    retrieval_top_k: int = Field(
        default=5, ge=1, le=20, description="Number of chunks to retrieve per query"
    )
    chunk_size: int = Field(default=512, ge=128, le=4096, description="Token size per chunk")
    chunk_overlap: int = Field(default=64, ge=0, le=512, description="Token overlap between chunks")

    # --- Sub-settings (populated from prefixed env vars) ---
    azure_openai: AzureOpenAISettings = Field(default_factory=AzureOpenAISettings)
    azure_search: AzureSearchSettings = Field(default_factory=AzureSearchSettings)
    azure_blob: AzureBlobSettings = Field(default_factory=AzureBlobSettings)
    entra: EntraIDSettings = Field(default_factory=EntraIDSettings)

    @field_validator("debug")
    @classmethod
    def no_debug_in_production(cls, value: bool, info: object) -> bool:  # noqa: ANN001
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
