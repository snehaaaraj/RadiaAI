import { useMemo, useState } from 'react';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
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
import type {
  ApplyFindingDispositionRequest,
  FindingDisposition,
  FindingDispositionStatus,
  ReviewFinding,
} from '@/types/api';
import { ReviewStatusChip } from './ReviewStatusChip';

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
    <Accordion disableGutters>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Box display="flex" width="100%" alignItems="center" justifyContent="space-between" pr={1}>
          <Box>
            <Typography variant="subtitle2" fontWeight={700}>
              {finding.category}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {finding.reviewer} • {finding.severity}
            </Typography>
          </Box>
          <Stack direction="row" spacing={1} alignItems="center">
            <Chip label={finding.pass_fail} size="small" variant="outlined" />
            <ReviewStatusChip status={finding.status} />
          </Stack>
        </Box>
      </AccordionSummary>
      <AccordionDetails>
        <Stack spacing={1.5}>
          <Typography variant="body2">
            <strong>Rule:</strong> {finding.rule}
          </Typography>
          <Typography variant="body2">
            <strong>Explanation:</strong> {finding.explanation}
          </Typography>
          <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
            <strong>Evidence:</strong> {finding.evidence}
          </Typography>
          <Typography variant="body2">
            <strong>Recommendation:</strong> {finding.recommendation}
          </Typography>
          <Typography variant="body2">
            <strong>Reference:</strong> {finding.reference}
          </Typography>

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

