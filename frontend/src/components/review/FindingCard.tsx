import { useMemo, useState } from 'react';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Chip from '@mui/material/Chip';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import Link from '@mui/material/Link';
import type {
  ApplyFindingDispositionRequest,
  FindingSeverity,
  FindingDisposition,
  FindingDispositionStatus,
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
    <Accordion
      disableGutters
      sx={{
        borderLeft: '5px solid',
        borderLeftColor:
          finding.severity === 'Critical' || finding.severity === 'High'
            ? 'error.main'
            : finding.severity === 'Medium'
              ? 'warning.main'
              : 'info.main',
        borderRadius: '18px !important',
        overflow: 'hidden',
      }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Box display="flex" width="100%" alignItems="center" justifyContent="space-between" pr={1}>
          <Box minWidth={0}>
            <Stack direction="row" gap={1} flexWrap="wrap" alignItems="center" mb={0.5}>
              <Chip label={finding.category} size="small" color="primary" variant="outlined" />
              <Chip
                label={finding.severity}
                size="small"
                color={SEVERITY_COLOR[finding.severity]}
              />
            </Stack>
            <Typography variant="subtitle1" fontWeight={800}>
              {finding.category}
            </Typography>
            <Typography variant="body2" color="text.secondary" noWrap>
              {finding.reviewer} • {finding.rule}
            </Typography>
          </Box>
          <Stack direction="row" spacing={1} alignItems="center">
            <Chip label={finding.pass_fail} size="small" variant="outlined" />
            <ReviewStatusChip status={finding.status} />
          </Stack>
        </Box>
      </AccordionSummary>
      <AccordionDetails>
        <Stack spacing={2}>
          <Alert
            severity={SEVERITY_COLOR[finding.severity]}
            variant="outlined"
            sx={{ alignItems: 'center' }}
          >
            <Typography variant="body2" fontWeight={700}>
              Suggested change
            </Typography>
            <Typography variant="body2">{finding.recommendation}</Typography>
          </Alert>

          <Box
            sx={{
              p: 1.5,
              borderRadius: 3,
              bgcolor: 'action.hover',
              border: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Typography variant="overline" color="text.secondary">
              Why this was flagged
            </Typography>
            <Typography variant="body2" mt={0.5}>
              {finding.explanation}
            </Typography>
          </Box>

          <Box
            sx={{
              p: 1.5,
              borderRadius: 3,
              border: '1px dashed',
              borderColor: 'divider',
              background:
                'linear-gradient(180deg, rgba(27,79,216,0.04), rgba(27,79,216,0.00))',
            }}
          >
            <Typography variant="overline" color="text.secondary">
              Observed source text
            </Typography>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', mt: 0.75 }}>
              {finding.evidence}
            </Typography>
          </Box>

          <Box
            sx={{
              p: 1.5,
              borderRadius: 3,
              border: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Stack spacing={0.75}>
              <Typography variant="overline" color="text.secondary">
                Standards source
              </Typography>
              <Typography variant="body2" fontWeight={700}>
                {finding.reference_title ?? finding.reference}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {finding.reference}
              </Typography>
              <Typography variant="body2">
                {finding.reference_url ? (
                  <Link href={finding.reference_url} target="_blank" rel="noopener noreferrer" underline="hover">
                    Open source document
                  </Link>
                ) : (
                  'No direct source URL provided.'
                )}
              </Typography>
            </Stack>
          </Box>

          {onApplyDisposition && (
            <>
              <Divider sx={{ my: 1 }} />
              <Typography variant="subtitle2" fontWeight={700}>
                Reviewer Disposition
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
  );
}
