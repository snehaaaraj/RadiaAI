import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { ApplyFindingDispositionRequest, ReviewFinding } from '@/types/api';
import { FindingCard } from './FindingCard';

interface ReviewChangeSetProps {
  findings: ReviewFinding[];
  title?: string;
  description?: string;
  reviewId?: string | null;
  onApplyDisposition?: (reviewId: string, payload: ApplyFindingDispositionRequest) => void;
  isApplyingDisposition?: boolean;
}

export function ReviewChangeSet({
  findings,
  title = 'Recommended changes',
  description = 'Read the recommended edit first, then the source of truth. Expand Details for context and actions.',
  reviewId,
  onApplyDisposition,
  isApplyingDisposition = false,
}: ReviewChangeSetProps) {
  if (findings.length === 0) {
    return <Alert severity="success">No changes were proposed for this review.</Alert>;
  }

  return (
    <Stack spacing={1.5}>
      <Box>
        <Typography variant="h6" fontWeight={800} gutterBottom>
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {description}
        </Typography>
      </Box>

      {findings.map((finding, index) => (
        <FindingCard
          key={`${finding.category}-${index}`}
          finding={finding}
          index={index}
          reviewId={reviewId}
          onApplyDisposition={onApplyDisposition}
          isApplyingDisposition={isApplyingDisposition}
        />
      ))}
    </Stack>
  );
}
