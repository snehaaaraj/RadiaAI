# Error Handling

## Summary

The API uses a consistent error envelope, logs request-correlated diagnostic
context, and avoids returning unhandled exception tracebacks. The frontend
normalizes API and JavaScript errors for display. This document describes the
current behavior and its known UI coverage.

## Current behavior

### Backend errors

#### Error context helpers (`app/core/error_context.py`)

`enrich_error_detail()` and `format_error_for_user()` are available to service
code that needs them; they are not automatically applied to every exception.

#### Domain exceptions (`app/core/exceptions.py`)
Domain exceptions carry an error code, HTTP status, message, and optional detail:

- **AzureServiceError**: Includes service, operation, and original error
- **EmbeddingError**: Includes model name
- **SearchError**: Includes index name and truncated query
- **LLMError**: Includes model name
- **IngestionError**: Includes filename and failure stage

The global handlers in `app/main.py` return domain details in the error envelope,
format request-validation failures as `VALIDATION_ERROR`, and return a generic
`INTERNAL_ERROR` for unexpected exceptions while logging their traceback
internally. Request IDs are included in responses and propagated into structured
logs.

#### Debugging Jama writes

The Jama write alert displays the upstream HTTP status, method, and resource
when Jama returns an otherwise unclassified HTTP error. In browser DevTools,
filter Network requests for `jama-write` and inspect the failed POST's Response.
Use `request_id` to locate the matching `domain_exception` in backend logs.
`error.detail` includes `jama_status_code`, `operation`, `request_method`,
`request_content_type`, and `response_content_type`. The application's HTTP 502
is a gateway error; `jama_status_code` identifies Jama's actual rejection.
When Jama returns a nonempty string at `meta.message` in its JSON error
response, the message is included in the alert and `error.detail.jama_message`.
It is normalized to one line and truncated after 1,000 characters.

Jama item PATCH requests use `Content-Type: application/json` with a JSON Patch
array, as in the
[Jama-maintained Python client's `patch_item`](https://github.com/jamasoftware-ps/py-jama-rest-client/blob/master/py_jama_rest_client/client.py).
Using `application/json-patch+json` can cause HTTP 415.

Apart from the selected `meta.message` field, upstream response bodies are not
copied into logs or API errors because they may contain private requirement data.
Jama's message may itself quote submitted values; redact it before sharing.
When the status and metadata are not
enough, reproduce against a test item with the backend debugger paused in
`JamaClient._request`'s `HTTPStatusError` handler and inspect
`exc.response.text` locally. Never share credentials, authorization headers,
cookies, or unredacted response bodies.

### Frontend errors

#### ErrorDisplay component (`frontend/src/components/ErrorDisplay.tsx`)
- Displays structured error information
- Shows user-friendly error titles
- Provides actionable suggestions
- Collapsible details section
- Copy error details to clipboard
- Retry functionality
- Context-aware suggestions based on error code

#### Current page coverage

The individual Requirement Review and Set Review pages use `ErrorDisplay`.
Callers can provide context and a retry callback; other pages may use their own
inline or page-specific error presentation.

## Error Information Structure

### Backend Error Response
```json
{
  "success": false,
  "error": {
    "code": "LLM_ERROR",
    "message": "Chat completion failed with model gpt-5",
    "detail": {
      "service": "Azure OpenAI",
      "operation": "chat_completion",
      "model": "gpt-5",
      "message_count": 3,
      "original_error": "Rate limit exceeded"
    }
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Frontend Display
- **Title**: User-friendly error title (e.g., "AI Model Error")
- **Message**: Clear description of what went wrong
- **Context**: Where the error occurred (e.g., "Requirement Review")
- **Suggestion**: Actionable recovery steps
- **Details**: Expandable technical details for debugging
- **Retry**: Optional retry button

`ErrorDisplay` recognizes the codes below. Other codes fall back to the generic
title; code-specific suggestions are shown only where available.

## Error Codes and Suggestions

| Error Code | User-Friendly Title | UI suggestion |
|------------|---------------------|---------------|
| `NETWORK_ERROR` | Network Connection Error | Check the connection and retry |
| `TIMEOUT_ERROR` | Request Timed Out | Retry the individual requirement |
| `RATE_LIMITED` | Rate Limit Exceeded | Wait, then retry failed items |
| `HTTP_ERROR` | Unexpected Server Response | No code-specific suggestion |
| `VALIDATION_ERROR` | Validation Error | No code-specific suggestion |
| `DOCUMENT_NOT_FOUND` | Document Not Found | No code-specific suggestion |
| `INDEX_NOT_FOUND` | Search Index Not Found | Contact support |
| `AZURE_SERVICE_ERROR` | Azure Service Error | No code-specific suggestion |
| `EMBEDDING_ERROR` | Embedding Generation Failed | Retry when the service is available |
| `SEARCH_ERROR` | Search Failed | Check the search index/service |
| `LLM_ERROR` | AI Model Error | Check service availability or rate limits |
| `INGESTION_ERROR` | Document Processing Failed | Check the file/stage when a stage is provided |
| `AUTHENTICATION_REQUIRED` | Authentication Required | Sign in again |
| `FORBIDDEN` | Access Denied | Contact an administrator |
| `CONFIGURATION_ERROR` | Configuration Error | Contact support |
| `INTERNAL_ERROR` | Internal Server Error | No code-specific suggestion |

## Benefits

1. **Better Debugging**: Detailed context helps identify root cause quickly
2. **User-Friendly**: Clear messages instead of technical jargon
3. **Actionable**: Suggestions guide users toward resolution
4. **Production-Ready**: Request IDs for tracing across logs
5. **Developer-Friendly**: Copy feature for bug reports
6. **Retry Support**: Users can retry failed operations without refresh

## Usage Examples

### Backend: Raising Enhanced Errors
```python
from app.core.exceptions import LLMError

try:
    response = openai_client.chat_completion(messages)
except Exception as e:
    raise LLMError(
        message=f"Chat completion failed with model {model_name}",
        model=model_name,
        original_error=str(e),
        detail={"message_count": len(messages)}
    )
```

### Frontend: Displaying Errors
```tsx
{isError && (
  <ErrorDisplay
    error={error}
    context="Requirement Review"
    onRetry={() => handleRetry()}
  />
)}
```

## Known scope and follow-up

`ErrorDisplay` is not a global error boundary and is not used by every page or
component. Remaining opportunities include:

1. Review remaining service/client paths for consistent structured context.
2. Extend `ErrorDisplay` to additional user-facing flows where a retry is useful.
3. Consider React error boundaries for component-render failures.
4. Consider error analytics for tracking common failures.

## Validation

Use the backend and frontend test suites for automated coverage. For a manual
check, exercise a retryable error on Requirement Review or Set Review and verify
the message, optional suggestion, request ID/details, retry action, and
copy-details control when those values are present.
