import { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import { useRequirementReview } from '@/hooks/useRequirementReview';
import { useApplyFindingDisposition } from '@/hooks/useReviewHistory';
import { FindingCard } from '@/components/review/FindingCard';
import { ReviewStatusChip } from '@/components/review/ReviewStatusChip';

const REQUIREMENT_LEVELS = ['aircraft', 'system', 'subsystem', 'component'] as const;

export default function RequirementReview() {
  const [requirementId, setRequirementId] = useState('');
  const [requirementLevel, setRequirementLevel] = useState<string>('system');
  const [text, setText] = useState('');

  const {
    mutate: runReview,
    data: result,
    isPending,
    isError,
    error,
  } = useRequirementReview();
  const { mutate: applyDisposition, isPending: isApplyingDisposition } = useApplyFindingDisposition();

  const canSubmit = useMemo(() => text.trim().length > 0, [text]);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={700}>
          Individual Requirement Review
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Deterministic review across language, structure, and verifiability categories.
        </Typography>
      </Box>

      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Stack spacing={2}>
          <TextField
            size="small"
            label="Requirement ID"
            value={requirementId}
            onChange={(event) => setRequirementId(event.target.value)}
            placeholder="REQ-1234"
          />
          <TextField
            select
            size="small"
            label="Requirement Level"
            value={requirementLevel}
            onChange={(event) => setRequirementLevel(event.target.value)}
          >
            {REQUIREMENT_LEVELS.map((level) => (
              <MenuItem key={level} value={level}>
                {level}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Requirement Text"
            multiline
            minRows={5}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="The subsystem shall ..."
          />
          <Box>
            <Button
              variant="contained"
              disabled={!canSubmit || isPending}
              onClick={() =>
                runReview({
                  requirement_id: requirementId || undefined,
                  requirement_level: requirementLevel,
                  text: text.trim(),
                })
              }
            >
              Run deterministic review
            </Button>
          </Box>
        </Stack>
      </Paper>

      {isError && <Alert severity="error">Review failed: {(error as Error).message}</Alert>}

      {result && (
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Stack spacing={2}>
            <Box display="flex" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1}>
              <Typography variant="h6" fontWeight={700}>
                Review Result
              </Typography>
              <ReviewStatusChip status={result.overall} size="medium" />
            </Box>
            {result.review_id && (
              <Typography variant="caption" color="text.secondary">
                Review ID: {result.review_id}
              </Typography>
            )}
            <Box display="flex" gap={1} flexWrap="wrap">
              {result.category_results.map((category) => (
                <Chip
                  key={`${category.category}-${category.status}`}
                  label={`${category.category}: ${category.status}`}
                  variant="outlined"
                  size="small"
                />
              ))}
            </Box>
            <Divider />
            <Stack spacing={1.5}>
              {result.findings.length === 0 ? (
                <Alert severity="success">No findings. Requirement is acceptable.</Alert>
              ) : (
                result.findings.map((finding, index) => (
                  <FindingCard
                    key={`${finding.category}-${index}`}
                    finding={finding}
                    index={index}
                    reviewId={result.review_id}
                    onApplyDisposition={(reviewId, payload) =>
                      applyDisposition({ reviewId, payload })
                    }
                    isApplyingDisposition={isApplyingDisposition}
                  />
                ))
              )}
            </Stack>
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
