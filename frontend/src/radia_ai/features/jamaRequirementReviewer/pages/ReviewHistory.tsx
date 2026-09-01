import { useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import MenuItem from '@mui/material/MenuItem';
import Pagination from '@mui/material/Pagination';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { FindingCard } from '@/radia_ai/features/jamaRequirementReviewer/components/FindingCard';
import { ReviewIncompleteNotice } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewIncompleteNotice';
import { ReviewQualityBand } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewQualityBand';
import { ReviewStatusChip } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewStatusChip';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { useReviewHistory } from '@/radia_ai/features/jamaRequirementReviewer/hooks/useReviewHistory';
import type { FindingDispositionStatus, ReviewWorkflow } from '@/types/api';
import { getApiErrorMessage } from '@/utils/apiErrorMessage';
import { getReviewQualityScore } from '@/utils/reviewQuality';
import { isReviewFailed, isReviewIncomplete } from '@/utils/reviewCompletion';
import { reviewHistoryStyles } from './ReviewHistory.styles';

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

const PAGE_SIZE = 10;

export default function ReviewHistory() {
  const [workflow, setWorkflow] = useState<ReviewWorkflow | 'all'>('all');
  const [dispositionFilter, setDispositionFilter] = useState<FindingDispositionStatus | 'all'>('all');
  const [page, setPage] = useState(1);
  const selectedWorkflow = workflow === 'all' ? undefined : workflow;
  const { data, isLoading, isError, error } = useReviewHistory(selectedWorkflow, 50);

  const filteredEntries = useMemo(() => {
    if (!data?.entries) return [];
    if (dispositionFilter === 'all') return data.entries;
    return data.entries.filter((entry) =>
      entry.dispositions.some((d) => d.disposition === dispositionFilter)
    );
  }, [data?.entries, dispositionFilter]);

  const totalPages = Math.ceil(filteredEntries.length / PAGE_SIZE);
  const pagedEntries = filteredEntries.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // Reset to page 1 whenever filters change
  const handleWorkflowChange = (value: ReviewWorkflow | 'all') => {
    setWorkflow(value);
    setPage(1);
  };
  const handleDispositionChange = (value: FindingDispositionStatus | 'all') => {
    setDispositionFilter(value);
    setPage(1);
  };

  if (isLoading) return <LoadingSpinner message="Loading review history..." />;
  if (isError) return <Alert severity="error">Failed to load history: {getApiErrorMessage(error)}</Alert>;

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

      <Box sx={reviewHistoryStyles.filterRow}>
        <TextField
          select
          size="small"
          label="Workflow"
          value={workflow}
          onChange={(e) => handleWorkflowChange(e.target.value as ReviewWorkflow | 'all')}
          sx={reviewHistoryStyles.filterSelect}
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
          onChange={(e) => handleDispositionChange(e.target.value as FindingDispositionStatus | 'all')}
          sx={reviewHistoryStyles.filterSelect}
        >
          {DISPOSITION_OPTIONS.map((option) => (
            <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </TextField>

        {filteredEntries.length > 0 && (
          <Typography variant="body2" color="text.secondary" sx={reviewHistoryStyles.resultCount}>
            {filteredEntries.length} result{filteredEntries.length !== 1 ? 's' : ''}
          </Typography>
        )}
      </Box>

      <Stack spacing={2}>
        {pagedEntries.length === 0 ? (
          <Alert severity="info">No review history entries match the selected filters.</Alert>
        ) : (
          pagedEntries.map((entry) => (
            <Paper key={entry.review_id} variant="outlined" sx={reviewHistoryStyles.entryPaper}>
              <Stack spacing={1.5}>
                <Box sx={reviewHistoryStyles.entryHeader}>
                  <Typography variant="subtitle1" fontWeight={700}>
                    {entry.review_id}
                  </Typography>
                  <ReviewStatusChip status={entry.overall} />
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Workflow: {entry.workflow} • Subject: {entry.subject_id ?? 'N/A'} •{' '}
                  {new Date(entry.created_at).toLocaleString()}
                </Typography>
                {isReviewIncomplete(entry.completion) && (
                  <ReviewIncompleteNotice completion={entry.completion} />
                )}
                {/* A run that never evaluated anything has no score to show. */}
                {!isReviewFailed(entry.completion) && (
                  <>
                    <ReviewQualityBand
                      score={getReviewQualityScore(entry.overall, entry.findings)}
                    />
                    <Box sx={reviewHistoryStyles.categoryRow}>
                      {entry.category_results.map((category, index) => (
                        <Chip
                          key={`${entry.review_id}-${category.category}-${index}`}
                          label={`${category.category}: ${category.status}`}
                          size="small"
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  </>
                )}
                <Stack spacing={1}>
                  {entry.findings.map((finding, index) => {
                    const disposition = entry.dispositions.find((item) => item.finding_index === index);
                    // Filter findings based on disposition filter
                    if (dispositionFilter !== 'all' && disposition?.disposition !== dispositionFilter) {
                      return null;
                    }
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

      {totalPages > 1 && (
        <Box sx={reviewHistoryStyles.paginationRow}>
          <Pagination
            count={totalPages}
            page={page}
            onChange={(_e, value) => setPage(value)}
            color="primary"
            shape="rounded"
          />
        </Box>
      )}
    </Stack>
  );
}
