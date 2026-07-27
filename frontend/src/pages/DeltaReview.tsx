import { useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { FindingCard } from '@/components/review/FindingCard';
import { ReviewStatusChip } from '@/components/review/ReviewStatusChip';
import { useDeltaReview } from '@/hooks/useDeltaReview';
import { useApplyFindingDisposition } from '@/hooks/useReviewHistory';
import type { DeltaReviewInput } from '@/types/api';

const BASELINE_SAMPLE = JSON.stringify(
  [
    {
      requirement_id: 'REQ-001',
      text: 'The subsystem shall enable diagnostics within 2 seconds.',
      requirement_level: 'system',
      metadata: { parent_id: 'P-100', verification_method: 'test' },
    },
    {
      requirement_id: 'REQ-002',
      text: 'The subsystem shall provide telemetry every 1 second.',
      requirement_level: 'system',
      metadata: { parent_id: 'P-100', verification_method: 'analysis' },
    },
  ],
  null,
  2
);

const UPDATED_SAMPLE = JSON.stringify(
  [
    {
      requirement_id: 'REQ-001',
      text: 'The subsystem shall enable diagnostics within 1 second.',
      requirement_level: 'system',
      metadata: { parent_id: 'P-100', verification_method: 'test' },
    },
    {
      requirement_id: 'REQ-003',
      text: 'The subsystem shall provide built-in test under nominal conditions.',
      requirement_level: 'system',
      metadata: { parent_id: 'P-110', verification_method: 'inspection' },
    },
  ],
  null,
  2
);

const TRACE_SAMPLE = JSON.stringify(
  [
    {
      requirement_id: 'REQ-001',
      change_type: 'modified',
      previous_parent_id: 'P-090',
      current_parent_id: 'P-100',
    },
  ],
  null,
  2
);

export default function DeltaReview() {
  const [specificationId, setSpecificationId] = useState('SPEC-DELTA-1');
  const [baselineJson, setBaselineJson] = useState(BASELINE_SAMPLE);
  const [updatedJson, setUpdatedJson] = useState(UPDATED_SAMPLE);
  const [traceJson, setTraceJson] = useState(TRACE_SAMPLE);
  const [parseError, setParseError] = useState('');

  const {
    mutate: runDeltaReview,
    data: result,
    isPending,
    isError,
    error,
  } = useDeltaReview();
  const { mutate: applyDisposition, isPending: isApplyingDisposition } = useApplyFindingDisposition();

  const canSubmit = useMemo(() => baselineJson.trim() && updatedJson.trim(), [baselineJson, updatedJson]);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={700}>
          Delta Review
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Incremental deterministic review for changed requirements only.
        </Typography>
      </Box>

      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Stack spacing={2}>
          <TextField
            size="small"
            label="Specification ID"
            value={specificationId}
            onChange={(event) => setSpecificationId(event.target.value)}
          />
          <TextField
            label="Baseline requirements (JSON array)"
            multiline
            minRows={7}
            value={baselineJson}
            onChange={(event) => setBaselineJson(event.target.value)}
          />
          <TextField
            label="Updated requirements (JSON array)"
            multiline
            minRows={7}
            value={updatedJson}
            onChange={(event) => setUpdatedJson(event.target.value)}
          />
          <TextField
            label="Changed trace links (JSON array)"
            multiline
            minRows={5}
            value={traceJson}
            onChange={(event) => setTraceJson(event.target.value)}
          />
          <Box>
            <Button
              variant="contained"
              disabled={!canSubmit || isPending}
              onClick={() => {
                try {
                  const payload: DeltaReviewInput = {
                    specification_id: specificationId || undefined,
                    baseline_requirements: JSON.parse(baselineJson),
                    updated_requirements: JSON.parse(updatedJson),
                    changed_trace_links: traceJson.trim() ? JSON.parse(traceJson) : [],
                  };
                  setParseError('');
                  runDeltaReview(payload);
                } catch (parseException) {
                  setParseError((parseException as Error).message);
                }
              }}
            >
              Run delta review
            </Button>
          </Box>
          {parseError && <Alert severity="error">Invalid JSON input: {parseError}</Alert>}
        </Stack>
      </Paper>

      {isError && <Alert severity="error">Delta review failed: {(error as Error).message}</Alert>}

      {result && (
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Stack spacing={2}>
            <Box display="flex" justifyContent="space-between" alignItems="center" gap={1} flexWrap="wrap">
              <Typography variant="h6" fontWeight={700}>
                Delta Review Result
              </Typography>
              <ReviewStatusChip status={result.overall} size="medium" />
            </Box>
            {result.review_id && (
              <Typography variant="caption" color="text.secondary">
                Review ID: {result.review_id}
              </Typography>
            )}
            <Box display="flex" gap={1} flexWrap="wrap">
              <Chip label={`New: ${result.change_summary.new_requirement_ids.length}`} size="small" />
              <Chip
                label={`Modified: ${result.change_summary.modified_requirement_ids.length}`}
                size="small"
              />
              <Chip label={`Deleted: ${result.change_summary.deleted_requirement_ids.length}`} size="small" />
              <Chip
                label={`Trace changes: ${result.change_summary.changed_trace_link_requirement_ids.length}`}
                size="small"
              />
            </Box>
            <Divider />
            <Typography variant="subtitle1" fontWeight={700}>
              Changed Requirement Findings
            </Typography>
            {result.reviewed_requirements.length === 0 ? (
              <Alert severity="success">No changed requirements to review.</Alert>
            ) : (
              result.reviewed_requirements.map((reviewedRequirement) => (
                <Paper key={reviewedRequirement.requirement_id} variant="outlined" sx={{ p: 1.5 }}>
                  <Stack spacing={1.5}>
                    <Box display="flex" justifyContent="space-between" alignItems="center" gap={1}>
                      <Typography variant="subtitle2">{reviewedRequirement.requirement_id}</Typography>
                      <ReviewStatusChip status={reviewedRequirement.overall} />
                    </Box>
                    {reviewedRequirement.findings.map((finding, index) => (
                      <FindingCard
                        key={`${reviewedRequirement.requirement_id}-${index}`}
                        finding={finding}
                        index={index}
                        reviewId={result.review_id}
                        onApplyDisposition={(reviewId, payload) =>
                          applyDisposition({ reviewId, payload })
                        }
                        isApplyingDisposition={isApplyingDisposition}
                      />
                    ))}
                  </Stack>
                </Paper>
              ))
            )}
            {result.requirement_set_findings.length > 0 && (
              <>
                <Divider />
                <Typography variant="subtitle1" fontWeight={700}>
                  Requirement Set Findings (Changed Items Scope)
                </Typography>
                <Stack spacing={1.5}>
                  {result.requirement_set_findings.map((finding, index) => (
                    <FindingCard
                      key={`set-finding-${index}`}
                      finding={finding}
                      index={index}
                      reviewId={result.review_id}
                      onApplyDisposition={(reviewId, payload) =>
                        applyDisposition({ reviewId, payload })
                      }
                      isApplyingDisposition={isApplyingDisposition}
                    />
                  ))}
                </Stack>
              </>
            )}
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
