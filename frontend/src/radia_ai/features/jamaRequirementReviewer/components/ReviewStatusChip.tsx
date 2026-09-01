import Chip from '@mui/material/Chip';
import type { ReviewStatus } from '@/types/api';

interface ReviewStatusChipProps {
  status: ReviewStatus;
  size?: 'small' | 'medium';
}

const STATUS_COLOR: Record<ReviewStatus, 'success' | 'warning' | 'error' | 'default'> = {
  Acceptable: 'success',
  'Revision Recommended': 'warning',
  Unacceptable: 'error',
  // Neutral on purpose: an unevaluated subject is neither a pass nor a failure.
  'Not Evaluated': 'default',
};

export function ReviewStatusChip({ status, size = 'small' }: ReviewStatusChipProps) {
  return <Chip label={status} color={STATUS_COLOR[status]} size={size} />;
}

