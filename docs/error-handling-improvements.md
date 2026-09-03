# Error Handling Improvements

## Summary

Enhanced error handling system with detailed context and user-friendly error messages to help identify and recover from failures in production.

## Changes Made

### Backend Enhancements

#### 1. New Error Context Utilities (`app/core/error_context.py`)
- `enrich_error_detail()`: Adds execution context to errors
- `format_error_for_user()`: Formats user-friendly error messages

#### 2. Enhanced Exception Classes (`app/core/exceptions.py`)
Updated exception classes with structured context:

- **AzureServiceError**: Now includes service, operation, and original error
- **EmbeddingError**: Includes model name and text count
- **SearchError**: Includes index name and truncated query
- **LLMError**: Includes model name and message count
- **IngestionError**: Includes filename and failure stage

#### 3. Updated Azure Clients (`app/core/azure_clients.py`)
- `OpenAIClient.generate_embeddings()`: Wraps errors with context
- `OpenAIClient.chat_completion()`: Wraps errors with context
- Better logging with structured context

### Frontend Enhancements

#### 1. New ErrorDisplay Component (`components/ErrorDisplay.tsx`)
- Displays structured error information
- Shows user-friendly error titles
- Provides actionable suggestions
- Collapsible details section
- Copy error details to clipboard
- Retry functionality
- Context-aware suggestions based on error code

#### 2. Updated Pages
- **RequirementReview**: Now uses `ErrorDisplay` component with retry functionality

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

## Error Codes and Suggestions

| Error Code | User-Friendly Title | Auto-Generated Suggestion |
|------------|---------------------|---------------------------|
| `NETWORK_ERROR` | Network Connection Error | Check internet connection |
| `EMBEDDING_ERROR` | Embedding Generation Failed | Service temporarily unavailable |
| `LLM_ERROR` | AI Model Error | Rate limit or service unavailable |
| `SEARCH_ERROR` | Search Failed | Index may not be initialized |
| `INGESTION_ERROR` | Document Processing Failed | Check file format |
| `AUTHENTICATION_REQUIRED` | Authentication Required | Please log in |
| `FORBIDDEN` | Access Denied | Contact administrator |
| `CONFIGURATION_ERROR` | Configuration Error | Contact support |

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

## Next Steps

To fully implement error handling across the application:

1. **Update remaining Azure clients** (SearchService, BlobStorageClient)
2. **Add error handling to ingestion service** with stage tracking
3. **Update all frontend pages** to use ErrorDisplay
4. **Add error boundaries** for React component crashes
5. **Implement error analytics** to track common failures

## Testing

Test the error handling by:
1. Disconnecting network → should show NETWORK_ERROR
2. Invalid credentials → should show AZURE_SERVICE_ERROR with details
3. Rate limiting → should show LLM_ERROR with rate limit suggestion
4. Check that request IDs appear in both logs and UI
5. Verify copy-to-clipboard works for bug reports
