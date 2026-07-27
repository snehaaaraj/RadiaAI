import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { FindingCard } from '@/components/review/FindingCard';
import { ReviewStatusChip } from '@/components/review/ReviewStatusChip';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { useApplyFindingDisposition, useReviewHistory } from '@/hooks/useReviewHistory';
import type { ReviewWorkflow } from '@/types/api';

const WORKFLOW_OPTIONS: Array<{ label: string; value: ReviewWorkflow | 'all' }> = [
  { label: 'All workflows', value: 'all' },
  { label: 'Individual requirement', value: 'requirement' },
  { label: 'Requirement set', value: 'requirement-set' },
  { label: 'Delta', value: 'delta' },
];

export default function ReviewHistory() {
  const [workflow, setWorkflow] = useState<ReviewWorkflow | 'all'>('all');
  const selectedWorkflow = workflow === 'all' ? undefined : workflow;
  const { data, isLoading, isError, error } = useReviewHistory(selectedWorkflow, 50);
  const { mutate: applyDisposition, isPending: isApplyingDisposition } = useApplyFindingDisposition();

  if (isLoading) return <LoadingSpinner message="Loading review history..." />;
  if (isError) return <Alert severity="error">Failed to load history: {(error as Error).message}</Alert>;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={700}>
          Review History
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Browse completed review runs and apply reviewer dispositions.
        </Typography>
      </Box>

      <Box maxWidth={320}>
        <TextField
          fullWidth
          select
          size="small"
          label="Workflow Filter"
          value={workflow}
          onChange={(event) => setWorkflow(event.target.value as ReviewWorkflow | 'all')}
        >
          {WORKFLOW_OPTIONS.map((option) => (
            <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </TextField>
      </Box>

      <Stack spacing={2}>
        {data?.entries.length === 0 ? (
          <Alert severity="info">No review history entries yet.</Alert>
        ) : (
          data?.entries.map((entry) => (
            <Paper key={entry.review_id} variant="outlined" sx={{ p: 2.5 }}>
              <Stack spacing={1.5}>
                <Box display="flex" justifyContent="space-between" alignItems="center" gap={1} flexWrap="wrap">
                  <Typography variant="subtitle1" fontWeight={700}>
                    {entry.review_id}
                  </Typography>
                  <ReviewStatusChip status={entry.overall} />
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Workflow: {entry.workflow} • Subject: {entry.subject_id ?? 'N/A'} •{' '}
                  {new Date(entry.created_at).toLocaleString()}
                </Typography>
                <Box display="flex" gap={1} flexWrap="wrap">
                  {entry.category_results.map((category, index) => (
                    <Chip
                      key={`${entry.review_id}-${category.category}-${index}`}
                      label={`${category.category}: ${category.status}`}
                      size="small"
                      variant="outlined"
                    />
                  ))}
                </Box>
                <Stack spacing={1}>
                  {entry.findings.map((finding, index) => {
                    const disposition = entry.dispositions.find((item) => item.finding_index === index);
                    return (
                      <FindingCard
                        key={`${entry.review_id}-${index}`}
                        finding={finding}
                        index={index}
                        reviewId={entry.review_id}
                        disposition={disposition}
                        onApplyDisposition={(reviewId, payload) =>
                          applyDisposition({ reviewId, payload })
                        }
                        isApplyingDisposition={isApplyingDisposition}
                      />
                    );
                  })}
                </Stack>
              </Stack>
            </Paper>
          ))
        )}
      </Stack>
    </Stack>
  );
}
