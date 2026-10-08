"""
Application configuration loaded from environment variables via Pydantic Settings.

All Azure endpoints, keys, and deployment names must be provided through the
environment (or a .env file during local development). Nothing is hardcoded here.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal, cast

from pydantic import AnyHttpUrl, Field, StringConstraints, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env location: check backend/.env first, then project root .env
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent  # RadiaAi-2.0/
_ENV_FILE = (
    str(_BACKEND_DIR / ".env") if (_BACKEND_DIR / ".env").exists() else str(_PROJECT_ROOT / ".env")
)

type DeploymentEnvironment = Literal["local", "development", "test", "staging", "production"]
type RequiredSetting = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# Environments where unauthenticated local development and the shared Jama service
# account are permitted. Every deployed environment must use Entra ID.
LOCAL_AUTH_BYPASS_ENVIRONMENTS: frozenset[str] = frozenset({"local", "test"})
# Environments that refuse to start without Entra ID configured.
ENTRA_REQUIRED_ENVIRONMENTS: frozenset[str] = frozenset({"staging", "production"})


def _reject_placeholder(value: str) -> str:
    normalized = value.casefold()
    if (normalized.startswith("<") and normalized.endswith(">")) or normalized in {
        "changeme",
        "example",
        "replace-me",
    }:
        raise ValueError("placeholder values are not allowed")
    return value


def _reject_placeholder_endpoint(value: AnyHttpUrl) -> AnyHttpUrl:
    hostname = (value.host or "").casefold()
    if hostname.startswith("example.") or hostname.startswith("<"):
        raise ValueError("placeholder Azure endpoints are not allowed")
    return value


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


def _jama_settings_factory() -> "JamaSettings":
    return cast(JamaSettings, cast(Any, JamaSettings)())


def _skillz_settings_factory() -> "SkillzSettings":
    return cast(SkillzSettings, cast(Any, SkillzSettings)())


class AzureOpenAISettings(BaseSettings):
    """Azure OpenAI service configuration."""

    model_config = SettingsConfigDict(
        env_prefix="AZURE_OPENAI_", env_file=_ENV_FILE, extra="ignore"
    )

    endpoint: AnyHttpUrl = Field(..., description="Azure OpenAI resource endpoint")
    api_key: RequiredSetting = Field(..., description="Azure OpenAI API key")
    api_version: str = Field(default="2024-10-21", description="API version")
    chat_deployment: RequiredSetting = Field(
        ..., description="Chat completion deployment name (e.g. gpt-4o)"
    )
    embedding_deployment: RequiredSetting = Field(
        ..., description="Embedding deployment name (e.g. text-embedding-3-large)"
    )
    embedding_dimensions: int = Field(default=3072, description="Embedding vector dimensions")
    max_tokens: int = Field(default=4096, description="Max tokens for chat completions")
    temperature: float = Field(default=0.0, description="Sampling temperature (0 = deterministic)")
    rag_chat_deployment: str | None = Field(
        default=None,
        description=(
            "Deployment used for the document Q&A chat endpoint/widget. This is "
            "latency-sensitive, so it defaults to a fast non-reasoning model rather "
            "than 'chat_deployment' (which may be a slower reasoning model such as "
            "gpt-5 used for the Jama Requirement Reviewer's deeper analysis). Falls "
            "back to 'chat_deployment' if unset."
        ),
    )
    rag_chat_max_tokens: int = Field(
        default=1200,
        description=(
            "Max tokens for the RAG chat endpoint's answers. Kept much lower than "
            "'max_tokens' (used by the reviewer) since chat answers are short and a "
            "large budget only adds latency without improving answer quality."
        ),
    )

    _validate_endpoint = field_validator("endpoint")(_reject_placeholder_endpoint)
    _validate_required_values = field_validator(
        "api_key", "chat_deployment", "embedding_deployment"
    )(_reject_placeholder)


class AzureSearchSettings(BaseSettings):
    """Azure AI Search service configuration."""

    model_config = SettingsConfigDict(
        env_prefix="AZURE_SEARCH_", env_file=_ENV_FILE, extra="ignore"
    )

    endpoint: AnyHttpUrl = Field(..., description="Azure AI Search endpoint")
    api_key: RequiredSetting = Field(..., description="Azure AI Search admin key")
    index_name: str = Field(default="radia-documents", description="Search index name")
    semantic_config_name: str = Field(
        default="radia-semantic-config", description="Semantic configuration name"
    )

    _validate_endpoint = field_validator("endpoint")(_reject_placeholder_endpoint)
    _validate_api_key = field_validator("api_key")(_reject_placeholder)


class AzureBlobSettings(BaseSettings):
    """Azure Blob Storage configuration."""

    model_config = SettingsConfigDict(env_prefix="AZURE_BLOB_", env_file=_ENV_FILE, extra="ignore")

    connection_string: RequiredSetting = Field(..., description="Blob Storage connection string")
    container_name: str = Field(
        default="radia-documents", description="Blob container for uploaded documents"
    )

    @field_validator("connection_string")
    @classmethod
    def validate_connection_string(cls, value: str) -> str:
        """Reject template connection strings that cannot authenticate."""
        normalized = value.casefold()
        if (
            "<" in value
            or "accountname=example" in normalized
            or "accountkey=example" in normalized
        ):
            raise ValueError("placeholder Azure Blob connection strings are not allowed")
        return _reject_placeholder(value)


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
    webhook_enabled: bool = Field(
        default=False,
        description=(
            "Enable a Microsoft Graph change-notification subscription so documents are "
            "automatically re-ingested whenever the SharePoint standards folder changes."
        ),
    )
    webhook_public_base_url: str = Field(
        default="",
        description=(
            "Public HTTPS base URL of this backend (e.g. https://myapp.vercel.app), used to "
            "build the Graph notificationUrl. Required when webhook_enabled is True."
        ),
    )

    @property
    def is_configured(self) -> bool:
        """True only when all credentials and site URL are set."""
        return bool(self.tenant_id and self.client_id and self.client_secret and self.site_url)

    @property
    def is_webhook_configured(self) -> bool:
        """True only when SharePoint is configured and the webhook has been enabled with a base URL."""
        return self.is_configured and self.webhook_enabled and bool(self.webhook_public_base_url)


class SkillzSettings(BaseSettings):
    """
    Skillz requirements-writing rules package (authoritative writing rules).

    The package is a zip in the SharePoint drive configured by ``SharePointSettings``
    and is read with the same credentials. Its rules govern the final
    recommendation synthesis only for the requirement levels listed in
    ``applicable_levels``.
    """

    model_config = SettingsConfigDict(env_prefix="SKILLZ_", env_file=_ENV_FILE, extra="ignore")

    enabled: bool = Field(default=True, description="Apply Skillz rules during synthesis")
    zip_path: str = Field(
        default=(
            "0. Reference Material/AI Reference Material/Skillz/"
            "acr-generator_Rev5.5_Issue1.0.zip"
        ),
        description="Path of the Skillz package zip within the SharePoint drive",
    )
    applicable_levels: list[str] = Field(
        default=["aircraft"],
        description="Requirement levels (case-insensitive) governed by this Skillz package",
    )
    cache_ttl_seconds: int = Field(
        default=3600,
        ge=0,
        description="How long a downloaded Skillz package is reused before re-fetching",
    )

    @field_validator("applicable_levels", mode="before")
    @classmethod
    def parse_applicable_levels(cls, value: str | list[str]) -> list[str]:
        """Accept a list, a JSON list string, or a comma-separated string."""
        if isinstance(value, list):
            return value
        import json

        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(level) for level in parsed]
        return [level.strip() for level in value.split(",") if level.strip()]


class JamaSettings(BaseSettings):
    """
    Jama Connect REST API settings.

    Credentials live only on the backend and are never exposed to the browser.
    Two authentication modes are supported:

      - ``basic``: username + password (or a Jama API ID / API key pair for
        Jama Cloud personal access).
      - ``oauth``: client_id + client_secret exchanged for a bearer token via
        the OAuth 2.0 client-credentials flow (POST /rest/oauth/token).
    """

    model_config = SettingsConfigDict(env_prefix="JAMA_", env_file=_ENV_FILE, extra="ignore")

    base_url: str = Field(
        default="",
        description="Jama instance root URL, e.g. https://yourorg.jamacloud.com (no /rest suffix)",
    )
    auth_type: Literal["basic", "oauth"] = Field(
        default="basic", description="Authentication mode: basic or oauth"
    )
    username: str = Field(default="", description="Username / API ID for basic auth")
    password: str = Field(default="", description="Password / API key for basic auth")
    client_id: str = Field(default="", description="OAuth client ID for client-credentials flow")
    client_secret: str = Field(
        default="", description="OAuth client secret for client-credentials flow"
    )
    api_version: str = Field(default="v1", description="Jama REST API version path segment")
    timeout_seconds: float = Field(
        default=20.0, description="Per-request timeout for Jama API calls (seconds)"
    )
    verify_ssl: bool = Field(
        default=True, description="Verify TLS certificates (disable only for self-hosted test)"
    )
    credential_encryption_key: str = Field(
        default="",
        description=(
            "Fernet key(s) used to encrypt each user's linked Jama API credentials at rest. "
            "Comma-separate several keys to rotate: the first encrypts, all decrypt. "
            'Generate with: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        ),
    )
    credential_container_name: str = Field(
        default="radia-user-secrets",
        description=(
            "Dedicated blob container for encrypted per-user Jama credentials, kept apart "
            "from the document container so ingestion can never read it."
        ),
    )
    require_email_match: bool = Field(
        default=True,
        description=(
            "Only allow linking a Jama account whose email/username matches the signed-in "
            "Microsoft account, so users cannot link someone else's Jama credentials."
        ),
    )

    @property
    def has_base_url(self) -> bool:
        """True when a Jama instance URL is configured (needed for per-user linking)."""
        return bool(self.base_url)

    @property
    def is_linking_configured(self) -> bool:
        """True when users can link their own Jama accounts."""
        return self.has_base_url and bool(self.credential_encryption_key.strip())

    @property
    def rest_base(self) -> str:
        """Return the fully-qualified REST base URL, e.g. https://org.jamacloud.com/rest/v1."""
        return f"{self.base_url.rstrip('/')}/rest/{self.api_version.strip('/')}"

    @property
    def token_url(self) -> str:
        """Return the OAuth token endpoint URL."""
        return f"{self.base_url.rstrip('/')}/rest/oauth/token"

    @property
    def is_configured(self) -> bool:
        """True only when a base URL and a complete shared service-account credential set are present."""
        if not self.base_url:
            return False
        if self.auth_type == "oauth":
            return bool(self.client_id and self.client_secret)
        return bool(self.username and self.password)


class EntraIDSettings(BaseSettings):
    """
    Microsoft Entra ID (Azure AD) configuration for validating API access tokens.

    ``client_id`` is the *API* app registration that exposes the delegated scope
    the SPA requests (e.g. ``api://<client_id>/access_as_user``) and defines the
    Radia app roles.
    """

    model_config = SettingsConfigDict(env_prefix="ENTRA_", env_file=_ENV_FILE, extra="ignore")

    tenant_id: str = Field(default="", description="Azure AD tenant ID")
    client_id: str = Field(default="", description="API app registration (client) ID")
    client_secret: str = Field(default="", description="Client secret (not used for validation)")
    audience: str = Field(
        default="",
        description="Token audience; defaults to api://<client_id>. The bare client_id is also accepted.",
    )
    authority_host: str = Field(
        default="https://login.microsoftonline.com",
        description="Entra authority host (change only for sovereign clouds)",
    )
    required_scope: str = Field(
        default="access_as_user",
        description="Delegated scope that user tokens must carry in the 'scp' claim",
    )
    require_app_role: bool = Field(
        default=True,
        description="Reject signed-in users that have no Radia app role assigned",
    )
    allow_app_tokens: bool = Field(
        default=False,
        description="Accept app-only (client-credentials) tokens that carry Radia app roles",
    )
    clock_skew_seconds: int = Field(
        default=120, ge=0, le=600, description="Leeway for exp/nbf/iat validation"
    )
    jwks_cache_ttl_seconds: int = Field(
        default=3600, ge=60, description="How long fetched signing keys are reused"
    )
    http_timeout_seconds: float = Field(
        default=10.0, gt=0, description="Timeout for fetching Entra signing keys"
    )

    @property
    def is_configured(self) -> bool:
        """True when tokens can be validated (tenant and API client id are set)."""
        return bool(self.tenant_id.strip() and self.client_id.strip())

    @property
    def accepted_audiences(self) -> list[str]:
        """Audiences accepted for v1 (api://...) and v2 (client id GUID) access tokens."""
        candidates = [self.audience, f"api://{self.client_id}", self.client_id]
        return list(dict.fromkeys(value.strip() for value in candidates if value.strip()))

    @property
    def accepted_issuers(self) -> list[str]:
        """Issuers for v2 and v1 access tokens of the configured tenant."""
        authority = self.authority_host.rstrip("/")
        return [f"{authority}/{self.tenant_id}/v2.0", f"https://sts.windows.net/{self.tenant_id}/"]

    @property
    def jwks_url(self) -> str:
        """Tenant signing-key endpoint (serves the keys for both v1 and v2 tokens)."""
        return f"{self.authority_host.rstrip('/')}/{self.tenant_id}/discovery/v2.0/keys"


class _ExplicitEnvironmentSettings(BaseSettings):
    """Read only an explicitly configured deployment environment."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: DeploymentEnvironment


def get_configured_environment() -> DeploymentEnvironment:
    """Return the explicitly configured deployment environment."""
    settings = cast(
        _ExplicitEnvironmentSettings,
        cast(Any, _ExplicitEnvironmentSettings)(),
    )
    return settings.environment


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
    environment: DeploymentEnvironment = Field(
        default="production",
        description=(
            "Deployment environment. Defaults to production so a deployment that forgets to "
            "set ENVIRONMENT fails closed instead of enabling the local auth bypass."
        ),
    )
    debug: bool = Field(default=False, description="Enable debug mode (never True in production)")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    ingestion_queue_name: str = Field(
        default="radia-ingestion", description="Azure Storage Queue for durable ingestion jobs"
    )
    ingestion_max_attempts: int = Field(
        default=5,
        ge=5,
        le=5,
        description="Queue-trigger delivery count; fixed at five to match poison handling",
    )
    ingestion_max_upload_bytes: int = Field(
        default=4 * 1024 * 1024,
        ge=1,
        le=4_500_000,
        description="Maximum upload size, kept below Vercel's request-body limit",
    )

    # --- API ---
    api_prefix: str = Field(default="/api/v1")
    allowed_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="CORS allowed origins",
    )
    allowed_origin_regex: str | None = Field(
        default=r"https://.*\.vercel\.app",
        description=(
            "Optional CORS origin regex (Vercel preview deployments). Set to an empty value "
            "when hosting internally so only ALLOWED_ORIGINS are trusted."
        ),
    )

    # --- Auth ---
    local_dev_user_roles: list[str] = Field(
        default=["Radia.Admin"],
        description=(
            "App roles granted to the synthetic user that is used only when ENVIRONMENT is "
            "local/test and Entra ID is not configured."
        ),
    )

    @field_validator("allowed_origin_regex", mode="before")
    @classmethod
    def blank_origin_regex_is_none(cls, value: str | None) -> str | None:
        """Treat an empty ALLOWED_ORIGIN_REGEX as 'no regex'."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("local_dev_user_roles", mode="before")
    @classmethod
    def parse_local_dev_user_roles(cls, value: str | list[str]) -> list[str]:
        """Accept a list, a JSON list string, or a comma-separated string."""
        if isinstance(value, list):
            return value
        import json

        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(role) for role in parsed]
        return [role.strip() for role in value.split(",") if role.strip()]

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
    jama: JamaSettings = Field(default_factory=_jama_settings_factory)
    skillz: SkillzSettings = Field(default_factory=_skillz_settings_factory)

    @field_validator("debug")
    @classmethod
    def no_debug_in_production(cls, value: bool, info: object) -> bool:
        """Prevent debug mode from being enabled in production environments."""
        # We check the raw values dict since environment may not be validated yet
        data = getattr(info, "data", {})
        if data.get("environment") == "production" and value:
            raise ValueError("debug=True is not allowed in the production environment")
        return value

    @property
    def allows_local_auth_bypass(self) -> bool:
        """Synthetic local user is allowed only for local/test runs without Entra configured."""
        return self.environment in LOCAL_AUTH_BYPASS_ENVIRONMENTS and not self.entra.is_configured

    @property
    def allows_shared_jama_account(self) -> bool:
        """The shared Jama service account is only for unauthenticated local/test runs."""
        return (
            self.environment in LOCAL_AUTH_BYPASS_ENVIRONMENTS
            and not self.entra.is_configured
            and self.jama.is_configured
        )


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """
    Return a cached singleton of AppSettings.

    Using lru_cache means the .env file is read exactly once at startup,
    and the same Settings object is reused for every dependency injection.
    Call get_settings.cache_clear() in tests to reset between test cases.
    """
    return AppSettings()
