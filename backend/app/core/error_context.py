"""
Error context enrichment utilities.

Provides helpers to add execution context to exceptions, making errors
more actionable in production environments.
"""

from typing import Any


def enrich_error_detail(
    operation: str,
    component: str,
    original_error: str | None = None,
    **additional_context: str | int | float | bool | None,
) -> dict[str, Any]:
    """
    Create a detailed error context dictionary.

    Args:
        operation: The operation that failed (e.g., "embedding_generation", "index_search")
        component: The component where the error occurred (e.g., "OpenAIClient", "SearchService")
        original_error: The original error message if wrapping another exception
        **additional_context: Any additional context-specific information

    Returns:
        Dictionary with structured error context

    Example:
        >>> enrich_error_detail(
        ...     operation="generate_embeddings",
        ...     component="OpenAIClient",
        ...     original_error="Rate limit exceeded",
        ...     model="text-embedding-3-large",
        ...     chunk_count=5
        ... )
        {
            "operation": "generate_embeddings",
            "component": "OpenAIClient",
            "original_error": "Rate limit exceeded",
            "model": "text-embedding-3-large",
            "chunk_count": 5
        }
    """
    context: dict[str, Any] = {
        "operation": operation,
        "component": component,
    }

    if original_error:
        context["original_error"] = original_error

    # Add additional context, filtering out None values
    for key, value in additional_context.items():
        if value is not None:
            context[key] = value

    return context


def format_error_for_user(
    operation: str,
    component: str,
    original_message: str,
    suggestion: str | None = None,
) -> str:
    """
    Format a user-friendly error message with context.

    Args:
        operation: The operation that failed
        component: The component where the error occurred
        original_message: The original error message
        suggestion: Optional suggestion for resolution

    Returns:
        Formatted error message

    Example:
        >>> format_error_for_user(
        ...     operation="search",
        ...     component="SearchService",
        ...     original_message="Index not found",
        ...     suggestion="Please contact support to initialize the search index"
        ... )
        "Search failed in SearchService: Index not found. Please contact support to initialize the search index."
    """
    message_parts = [f"{operation.replace('_', ' ').capitalize()} failed in {component}"]

    if original_message:
        message_parts.append(original_message)

    message = ": ".join(message_parts)

    if suggestion:
        message += f". {suggestion}"

    return message
