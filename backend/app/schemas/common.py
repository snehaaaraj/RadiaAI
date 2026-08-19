"""
Shared response envelope schemas.

All API responses are wrapped in a consistent envelope so clients always
have a predictable structure regardless of endpoint. This also makes it
straightforward to add pagination, request tracing, or API version fields
without breaking existing clients.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    """
    Standard success response envelope.

    Example JSON:
        {
          "success": true,
          "data": { ... },
          "request_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    """

    success: bool = True
    data: DataT
    request_id: str = Field(default="", description="Echo of X-Request-ID for tracing")


class ErrorDetail(BaseModel):
    """Machine-readable error information embedded in an error response."""

    code: str = Field(description="Stable error code (e.g. DOCUMENT_NOT_FOUND)")
    message: str = Field(description="Human-readable error message")
    detail: dict = Field(default_factory=dict, description="Optional additional context")


class ErrorResponse(BaseModel):
    """
    Standard error response envelope.

    Stack traces are never included. The 'detail' field may contain
    field-level validation errors or other safe context.

    Example JSON:
        {
          "success": false,
          "error": {
            "code": "DOCUMENT_NOT_FOUND",
            "message": "Document abc123 does not exist",
            "detail": {}
          },
          "request_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    """

    success: bool = False
    error: ErrorDetail
    request_id: str = Field(default="")


class PaginatedResponse(BaseModel, Generic[DataT]):
    """
    Paginated response envelope for list endpoints.

    Example JSON:
        {
          "success": true,
          "data": [...],
          "total": 42,
          "page": 1,
          "page_size": 10,
          "request_id": "..."
        }
    """

    success: bool = True
    data: list[DataT]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    request_id: str = Field(default="")
