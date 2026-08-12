import { useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { FindingCard } from '@/components/review/FindingCard';
import { ReviewQualityBand } from '@/components/review/ReviewQualityBand';
import { ReviewStatusChip } from '@/components/review/ReviewStatusChip';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { useReviewHistory } from '@/hooks/useReviewHistory';
import type { FindingDispositionStatus, ReviewWorkflow } from '@/types/api';
import { getReviewQualityScore } from '@/utils/reviewQuality';

const WORKFLOW_OPTIONS: Array<{ label: string; value: ReviewWorkflow | 'all' }> = [
  { label: 'All workflows', value: 'all' },
  { label: 'Individual requirement', value: 'requirement' },
  { label: 'Delta', value: 'delta' },
];

const DISPOSITION_OPTIONS: Array<{ label: string; value: FindingDispositionStatus | 'all' }> = [
  { label: 'All dispositions', value: 'all' },
  { label: 'Accepted', value: 'Accepted' },
  { label: 'Rejected', value: 'Rejected' },
  { label: 'Deferred', value: 'Deferred' },
];

export default function ReviewHistory() {
  const [workflow, setWorkflow] = useState<ReviewWorkflow | 'all'>('all');
  const [dispositionFilter, setDispositionFilter] = useState<FindingDispositionStatus | 'all'>('all');
  const selectedWorkflow = workflow === 'all' ? undefined : workflow;
  const { data, isLoading, isError, error } = useReviewHistory(selectedWorkflow, 50);

  const filteredEntries = useMemo(() => {
    if (!data?.entries) return [];
    if (dispositionFilter === 'all') return data.entries;
    return data.entries.filter((entry) =>
      entry.dispositions.some((d) => d.disposition === dispositionFilter)
    );
  }, [data?.entries, dispositionFilter]);

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

      <Box display="flex" gap={2} flexWrap="wrap">
        <TextField
          select
          size="small"
          label="Workflow"
          value={workflow}
          onChange={(event) => setWorkflow(event.target.value as ReviewWorkflow | 'all')}
          sx={{ minWidth: 200 }}
        >
          {WORKFLOW_OPTIONS.map((option) => (
            <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </TextField>

        <TextField
          select
          size="small"
          label="Disposition"
          value={dispositionFilter}
          onChange={(event) => setDispositionFilter(event.target.value as FindingDispositionStatus | 'all')}
          sx={{ minWidth: 200 }}
        >
          {DISPOSITION_OPTIONS.map((option) => (
            <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </TextField>
      </Box>

      <Stack spacing={2}>
        {filteredEntries.length === 0 ? (
          <Alert severity="info">No review history entries match the selected filters.</Alert>
        ) : (
          filteredEntries.map((entry) => (
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
                <ReviewQualityBand
                  score={getReviewQualityScore(entry.overall, entry.findings)}
                />
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
                        readOnly
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
