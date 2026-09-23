import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import RefreshIcon from '@mui/icons-material/Refresh';
import type { ReviewCompletion } from '@/types/api';
import {
  getCompletionMessage,
  getCompletionTitle,
  isReviewPartial,
  isRetryableFailure,
} from '@/utils/reviewCompletion';

interface ReviewIncompleteNoticeProps {
  completion?: ReviewCompletion | null;
  /** Optional retry handler — only offered for transient failures. */
  onRetry?: () => void;
  isRetrying?: boolean;
}

/**
 * Notice shown when the review engine did not evaluate the subject.
 *
 * This replaces the score and findings for a failed review, so an unevaluated
 * requirement is never rendered as a passing one.
 */
export function ReviewIncompleteNotice({
  completion,
  onRetry,
  isRetrying = false,
}: ReviewIncompleteNoticeProps) {
  const partial = isReviewPartial(completion);
  const showRetry = Boolean(onRetry) && isRetryableFailure(completion);

  return (
    <Alert
      severity={partial ? 'warning' : 'error'}
      action={
        showRetry ? (
          <Button
            color="inherit"
            size="small"
            startIcon={<RefreshIcon fontSize="small" />}
            onClick={onRetry}
            disabled={isRetrying}
          >
            {isRetrying ? 'Retrying…' : 'Retry review'}
          </Button>
        ) : undefined
      }
    >
      <AlertTitle>{getCompletionTitle(completion)}</AlertTitle>
      <Typography variant="body2">{getCompletionMessage(completion)}</Typography>
    </Alert>
  );
}
