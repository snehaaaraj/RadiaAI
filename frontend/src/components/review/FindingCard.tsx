import { useMemo, useState } from 'react';
import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Link from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import type {
  ApplyFindingDispositionRequest,
  FindingDisposition,
  FindingDispositionStatus,
  FindingSeverity,
  ReviewFinding,
} from '@/types/api';
import { ReviewStatusChip } from './ReviewStatusChip';

const SEVERITY_COLOR: Record<FindingSeverity, 'error' | 'warning' | 'info'> = {
  Critical: 'error',
  High: 'error',
  Medium: 'warning',
  Low: 'info',
};

interface FindingCardProps {
  finding: ReviewFinding;
  index: number;
  reviewId?: string | null;
  disposition?: FindingDisposition;
  onApplyDisposition?: (reviewId: string, payload: ApplyFindingDispositionRequest) => void;
  isApplyingDisposition?: boolean;
}

export function FindingCard({
  finding,
  index,
  reviewId,
  disposition,
  onApplyDisposition,
  isApplyingDisposition = false,
}: FindingCardProps) {
  const [selectedDisposition, setSelectedDisposition] = useState<FindingDispositionStatus | ''>(
    disposition?.disposition ?? ''
  );
  const [comment, setComment] = useState(disposition?.reviewer_comment ?? '');

  const canSubmitDisposition = useMemo(
    () => Boolean(reviewId && selectedDisposition && onApplyDisposition),
    [onApplyDisposition, reviewId, selectedDisposition]
  );

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        borderRadius: 3,
        borderLeft: '5px solid',
        borderLeftColor:
          finding.severity === 'Critical' || finding.severity === 'High'
            ? 'error.main'
            : finding.severity === 'Medium'
              ? 'warning.main'
              : 'info.main',
      }}
    >
      <Stack spacing={1.25}>
        <Box display="flex" alignItems="center" justifyContent="space-between" gap={1} flexWrap="wrap">
          <Stack direction="row" gap={1} flexWrap="wrap" alignItems="center">
            <Chip label={finding.category} size="small" color="primary" variant="outlined" />
            <Chip label={finding.severity} size="small" color={SEVERITY_COLOR[finding.severity]} />
            <Typography variant="subtitle2" fontWeight={800}>
              Change {index + 1}
            </Typography>
          </Stack>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            <Chip label={finding.pass_fail} size="small" variant="outlined" />
            <ReviewStatusChip status={finding.status} />
          </Stack>
        </Box>

        <Box
          sx={{
            p: 1.25,
            borderRadius: 2,
            bgcolor: 'action.hover',
          }}
        >
          <Typography variant="overline" color="text.secondary">
            What should change
          </Typography>
          <Typography variant="body2" mt={0.5}>
            {finding.recommendation}
          </Typography>
        </Box>

        <Box
          sx={{
            p: 1.25,
            borderRadius: 2,
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Stack spacing={0.5}>
            <Typography variant="overline" color="text.secondary">
              Source of truth
            </Typography>
            <Typography variant="body2" fontWeight={700}>
              {finding.reference_title ?? finding.reference}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {finding.reference}
            </Typography>
            {finding.reference_url && (
              <Link href={finding.reference_url} target="_blank" rel="noopener noreferrer" underline="hover">
                Open source standard
              </Link>
            )}
          </Stack>
        </Box>

        <Accordion
          disableGutters
          sx={{
            boxShadow: 'none',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 2,
            '&:before': { display: 'none' },
            overflow: 'hidden',
          }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2" fontWeight={700}>
              Details
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={1.5}>
              <Box>
                <Typography variant="overline" color="text.secondary">
                  Why was this flagged
                </Typography>
                <Typography variant="body2" mt={0.5}>
                  {finding.explanation}
                </Typography>
              </Box>

              <Box
                sx={{
                  p: 1.25,
                  borderRadius: 2,
                  border: '1px dashed',
                  borderColor: 'divider',
                }}
              >
                <Typography variant="overline" color="text.secondary">
                  Observed source text
                </Typography>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', mt: 0.5 }}>
                  {finding.evidence}
                </Typography>
              </Box>

              <Box
                sx={{
                  p: 1.25,
                  borderRadius: 2,
                  bgcolor: 'action.hover',
                }}
              >
                <Typography variant="overline" color="text.secondary">
                  What do we do about it
                </Typography>
                <Typography variant="body2" mt={0.5}>
                  {finding.recommendation}
                </Typography>
              </Box>

              {onApplyDisposition && (
                <>
                  <Divider />
                  <Typography variant="subtitle2" fontWeight={700}>
                    Reviewer disposition
                  </Typography>
                  <ToggleButtonGroup
                    exclusive
                    size="small"
                    value={selectedDisposition}
                    onChange={(_, value) => setSelectedDisposition(value ?? '')}
                  >
                    <ToggleButton value="Accepted">Accepted</ToggleButton>
                    <ToggleButton value="Rejected">Rejected</ToggleButton>
                    <ToggleButton value="Deferred">Deferred</ToggleButton>
                  </ToggleButtonGroup>
                  <TextField
                    multiline
                    minRows={2}
                    size="small"
                    placeholder="Reviewer comment"
                    value={comment}
                    onChange={(event) => setComment(event.target.value)}
                  />
                  <Box>
                    <Button
                      variant="contained"
                      size="small"
                      disabled={!canSubmitDisposition || isApplyingDisposition}
                      onClick={() => {
                        if (!reviewId || !selectedDisposition || !onApplyDisposition) return;
                        onApplyDisposition(reviewId, {
                          finding_index: index,
                          disposition: selectedDisposition,
                          reviewer_comment: comment,
                        });
                      }}
                    >
                      Save disposition
                    </Button>
                  </Box>
                </>
              )}
            </Stack>
          </AccordionDetails>
        </Accordion>
      </Stack>
    </Paper>
  );
}
