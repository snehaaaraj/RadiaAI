/**
 * Enhanced error message display component.
 *
 * Displays structured error messages with execution context to help
 * identify and recover from failures in production.
 */

import { Alert, AlertTitle, Box, Collapse, IconButton, Stack, Typography } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import { useState } from 'react';
import type { ErrorResponse } from '@/types/api';

interface ErrorDisplayProps {
  error: unknown;
  title?: string;
  context?: string;
  onRetry?: () => void;
}

/**
 * Extract structured error information from various error types.
 */
function extractErrorInfo(error: unknown): {
  code: string;
  message: string;
  detail: Record<string, unknown>;
  requestId: string;
} {
  // Structured ErrorResponse from backend
  if (error && typeof error === 'object' && 'error' in error) {
    const errorResponse = error as ErrorResponse;
    return {
      code: errorResponse.error.code,
      message: errorResponse.error.message,
      detail: errorResponse.error.detail,
      requestId: errorResponse.request_id,
    };
  }

  // Generic error object with message
  if (error && typeof error === 'object' && 'message' in error) {
    return {
      code: 'UNKNOWN_ERROR',
      message: String((error as { message: unknown }).message),
      detail: {},
      requestId: '',
    };
  }

  // Fallback
  return {
    code: 'UNKNOWN_ERROR',
    message: 'An unexpected error occurred',
    detail: {},
    requestId: '',
  };
}

/**
 * Get user-friendly title based on error code.
 */
function getErrorTitle(code: string): string {
  const titles: Record<string, string> = {
    NETWORK_ERROR: 'Network Connection Error',
    VALIDATION_ERROR: 'Validation Error',
    DOCUMENT_NOT_FOUND: 'Document Not Found',
    INDEX_NOT_FOUND: 'Search Index Not Found',
    AZURE_SERVICE_ERROR: 'Azure Service Error',
    EMBEDDING_ERROR: 'Embedding Generation Failed',
    SEARCH_ERROR: 'Search Failed',
    LLM_ERROR: 'AI Model Error',
    INGESTION_ERROR: 'Document Processing Failed',
    AUTHENTICATION_REQUIRED: 'Authentication Required',
    FORBIDDEN: 'Access Denied',
    CONFIGURATION_ERROR: 'Configuration Error',
    INTERNAL_ERROR: 'Internal Server Error',
  };

  return titles[code] || 'Error';
}

/**
 * Get user-friendly suggestions based on error context.
 */
function getSuggestion(code: string, detail: Record<string, unknown>): string | null {
  // Network errors
  if (code === 'NETWORK_ERROR') {
    return 'Please check your internet connection and try again.';
  }

  // Azure service errors with specific suggestions
  if (code === 'EMBEDDING_ERROR') {
    return 'The AI embedding service is temporarily unavailable. Please try again in a few moments.';
  }

  if (code === 'LLM_ERROR') {
    if (detail.original_error && String(detail.original_error).includes('rate limit')) {
      return 'Rate limit exceeded. Please wait a moment before trying again.';
    }
    return 'The AI model service is temporarily unavailable. Please try again.';
  }

  if (code === 'SEARCH_ERROR') {
    if (detail.index_name) {
      return `Search index "${detail.index_name}" may not be initialized. Contact support if the issue persists.`;
    }
    return 'The search service is temporarily unavailable. Please try again.';
  }

  if (code === 'INGESTION_ERROR' && detail.stage) {
    return `Document processing failed during ${detail.stage}. Please check the file format and try again.`;
  }

  // Auth errors
  if (code === 'AUTHENTICATION_REQUIRED') {
    return 'Please log in to continue.';
  }

  if (code === 'FORBIDDEN') {
    return 'You don\'t have permission to access this resource. Contact your administrator.';
  }

  // Configuration errors
  if (code === 'CONFIGURATION_ERROR' || code === 'INDEX_NOT_FOUND') {
    return 'System configuration issue detected. Please contact support.';
  }

  return null;
}

export function ErrorDisplay({ error, title, context, onRetry }: ErrorDisplayProps) {
  const [showDetails, setShowDetails] = useState(false);
  const [copied, setCopied] = useState(false);

  const errorInfo = extractErrorInfo(error);
  const displayTitle = title || getErrorTitle(errorInfo.code);
  const suggestion = getSuggestion(errorInfo.code, errorInfo.detail);

  const hasDetails = Object.keys(errorInfo.detail).length > 0 || errorInfo.requestId;

  const handleCopyDetails = () => {
    const detailsText = JSON.stringify(
      {
        code: errorInfo.code,
        message: errorInfo.message,
        detail: errorInfo.detail,
        requestId: errorInfo.requestId,
        context,
      },
      null,
      2
    );

    navigator.clipboard.writeText(detailsText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <Alert
      severity="error"
      action={
        hasDetails && (
          <Stack direction="row" spacing={1}>
            <IconButton
              size="small"
              onClick={handleCopyDetails}
              title={copied ? 'Copied!' : 'Copy error details'}
            >
              <ContentCopyIcon fontSize="small" />
            </IconButton>
            <IconButton
              size="small"
              onClick={() => setShowDetails(!showDetails)}
              title={showDetails ? 'Hide details' : 'Show details'}
            >
              {showDetails ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          </Stack>
        )
      }
    >
      <AlertTitle>{displayTitle}</AlertTitle>

      <Typography variant="body2" gutterBottom>
        {errorInfo.message}
      </Typography>

      {context && (
        <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
          Context: {context}
        </Typography>
      )}

      {suggestion && (
        <Typography variant="body2" sx={{ mt: 1, fontStyle: 'italic' }}>
          {suggestion}
        </Typography>
      )}

      {onRetry && (
        <Box sx={{ mt: 1 }}>
          <Typography
            component="a"
            variant="body2"
            onClick={onRetry}
            sx={{
              cursor: 'pointer',
              textDecoration: 'underline',
              '&:hover': { textDecoration: 'none' },
            }}
          >
            Try again
          </Typography>
        </Box>
      )}

      {hasDetails && (
        <Collapse in={showDetails} sx={{ mt: 2 }}>
          <Box
            sx={{
              bgcolor: 'background.paper',
              p: 2,
              borderRadius: 1,
              fontFamily: 'monospace',
              fontSize: '0.75rem',
            }}
          >
            <Stack spacing={1}>
              <Typography variant="caption" fontWeight="bold">
                Error Code:
              </Typography>
              <Typography variant="caption">{errorInfo.code}</Typography>

              {errorInfo.requestId && (
                <>
                  <Typography variant="caption" fontWeight="bold">
                    Request ID:
                  </Typography>
                  <Typography variant="caption">{errorInfo.requestId}</Typography>
                </>
              )}

              {Object.keys(errorInfo.detail).length > 0 && (
                <>
                  <Typography variant="caption" fontWeight="bold">
                    Details:
                  </Typography>
                  <Box component="pre" sx={{ m: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {JSON.stringify(errorInfo.detail, null, 2)}
                  </Box>
                </>
              )}
            </Stack>
          </Box>
        </Collapse>
      )}

      {copied && (
        <Typography variant="caption" color="success.main" sx={{ mt: 1, display: 'block' }}>
          Error details copied to clipboard
        </Typography>
      )}
    </Alert>
  );
}
