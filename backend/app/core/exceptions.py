"""
Custom exception hierarchy for Radia AI.

Design principles:
  - All application exceptions inherit from RadiaBaseException.
  - Each exception carries a human-readable message and an optional detail dict.
  - HTTP status codes are co-located with the exception class so handlers
    don't need to maintain a separate mapping.
  - Stack traces are never exposed in API responses (the error handler in
    main.py maps these to standardized error envelopes).
"""

from http import HTTPStatus


class RadiaBaseException(Exception):
    """Base class for all Radia AI application exceptions."""

    http_status: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, detail: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


# ---------------------------------------------------------------------------
# Configuration / startup errors
# ---------------------------------------------------------------------------


class ConfigurationError(RadiaBaseException):
    """Raised when required configuration is missing or invalid at startup."""

    http_status = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code = "CONFIGURATION_ERROR"


# ---------------------------------------------------------------------------
# Resource / not-found errors
# ---------------------------------------------------------------------------


class DocumentNotFoundError(RadiaBaseException):
    """Raised when a requested document does not exist."""

    http_status = HTTPStatus.NOT_FOUND
    error_code = "DOCUMENT_NOT_FOUND"


class IndexNotFoundError(RadiaBaseException):
    """Raised when the Azure AI Search index does not exist."""

    http_status = HTTPStatus.NOT_FOUND
    error_code = "INDEX_NOT_FOUND"


# ---------------------------------------------------------------------------
# Validation / client errors
# ---------------------------------------------------------------------------


class ValidationError(RadiaBaseException):
    """Raised when input validation fails beyond Pydantic's scope."""

    http_status = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_ERROR"


class UnsupportedFileTypeError(RadiaBaseException):
    """Raised when an uploaded file type is not supported for ingestion."""

    http_status = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = "UNSUPPORTED_FILE_TYPE"


# ---------------------------------------------------------------------------
# External service errors
# ---------------------------------------------------------------------------


class AzureServiceError(RadiaBaseException):
    """Raised when an Azure service call fails unexpectedly."""

    http_status = HTTPStatus.BAD_GATEWAY
    error_code = "AZURE_SERVICE_ERROR"


class EmbeddingError(AzureServiceError):
    """Raised when embedding generation fails."""

    error_code = "EMBEDDING_ERROR"


class SearchError(AzureServiceError):
    """Raised when a search query fails."""

    error_code = "SEARCH_ERROR"


class LLMError(AzureServiceError):
    """Raised when a chat completion call fails."""

    error_code = "LLM_ERROR"


# ---------------------------------------------------------------------------
# Auth errors
# ---------------------------------------------------------------------------


class AuthenticationError(RadiaBaseException):
    """Raised when a request is unauthenticated."""

    http_status = HTTPStatus.UNAUTHORIZED
    error_code = "AUTHENTICATION_REQUIRED"


class AuthorizationError(RadiaBaseException):
    """Raised when an authenticated user lacks permission for a resource."""

    http_status = HTTPStatus.FORBIDDEN
    error_code = "FORBIDDEN"


# ---------------------------------------------------------------------------
# Ingestion errors
# ---------------------------------------------------------------------------


class IngestionError(RadiaBaseException):
    """Raised when document ingestion fails."""

    http_status = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code = "INGESTION_ERROR"
