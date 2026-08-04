import { useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import { FileUploadZone } from '@/components/review/FileUploadZone';
import { FindingCard } from '@/components/review/FindingCard';
import { ReviewQualityBand } from '@/components/review/ReviewQualityBand';
import { ReviewStatusChip } from '@/components/review/ReviewStatusChip';
import { useDeltaReview } from '@/hooks/useDeltaReview';
import { useApplyFindingDisposition } from '@/hooks/useReviewHistory';
import type { DeltaReviewInput } from '@/types/api';
import { getReviewQualityScore } from '@/utils/reviewQuality';

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

type JsonInputMode = 'paste' | 'upload';

export default function DeltaReview() {
  const [specificationId, setSpecificationId] = useState('SPEC-DELTA-1');
  const [baselineJson, setBaselineJson] = useState(BASELINE_SAMPLE);
  const [updatedJson, setUpdatedJson] = useState(UPDATED_SAMPLE);
  const [traceJson, setTraceJson] = useState(TRACE_SAMPLE);
  const [parseError, setParseError] = useState('');

  const [baselineMode, setBaselineMode] = useState<JsonInputMode>('paste');
  const [updatedMode, setUpdatedMode] = useState<JsonInputMode>('paste');
  const [traceMode, setTraceMode] = useState<JsonInputMode>('paste');
  const [baselineFilename, setBaselineFilename] = useState('');
  const [updatedFilename, setUpdatedFilename] = useState('');
  const [traceFilename, setTraceFilename] = useState('');

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

          {/* Baseline */}
          <Box>
            <Typography variant="subtitle2" fontWeight={600} mb={0.75}>
              Baseline requirements
            </Typography>
            <ToggleButtonGroup
              size="small"
              value={baselineMode}
              exclusive
              onChange={(_, value: JsonInputMode | null) => {
                if (value) {
                  setBaselineMode(value);
                  if (value === 'paste') { setBaselineFilename(''); setBaselineJson(BASELINE_SAMPLE); }
                }
              }}
              sx={{ mb: 1 }}
            >
              <ToggleButton value="paste">Paste JSON</ToggleButton>
              <ToggleButton value="upload">Upload .json</ToggleButton>
            </ToggleButtonGroup>
            {baselineMode === 'paste' ? (
              <TextField
                fullWidth
                multiline
                minRows={7}
                value={baselineJson}
                onChange={(event) => setBaselineJson(event.target.value)}
              />
            ) : (
              <FileUploadZone
                accept=".json"
                label="Upload baseline requirements as a .json file"
                onFileContent={(content, filename) => { setBaselineJson(content); setBaselineFilename(filename); }}
                filename={baselineFilename}
                onClear={() => { setBaselineJson(''); setBaselineFilename(''); }}
              />
            )}
          </Box>

          {/* Updated */}
          <Box>
            <Typography variant="subtitle2" fontWeight={600} mb={0.75}>
              Updated requirements
            </Typography>
            <ToggleButtonGroup
              size="small"
              value={updatedMode}
              exclusive
              onChange={(_, value: JsonInputMode | null) => {
                if (value) {
                  setUpdatedMode(value);
                  if (value === 'paste') { setUpdatedFilename(''); setUpdatedJson(UPDATED_SAMPLE); }
                }
              }}
              sx={{ mb: 1 }}
            >
              <ToggleButton value="paste">Paste JSON</ToggleButton>
              <ToggleButton value="upload">Upload .json</ToggleButton>
            </ToggleButtonGroup>
            {updatedMode === 'paste' ? (
              <TextField
                fullWidth
                multiline
                minRows={7}
                value={updatedJson}
                onChange={(event) => setUpdatedJson(event.target.value)}
              />
            ) : (
              <FileUploadZone
                accept=".json"
                label="Upload updated requirements as a .json file"
                onFileContent={(content, filename) => { setUpdatedJson(content); setUpdatedFilename(filename); }}
                filename={updatedFilename}
                onClear={() => { setUpdatedJson(''); setUpdatedFilename(''); }}
              />
            )}
          </Box>

          {/* Trace links */}
          <Box>
            <Typography variant="subtitle2" fontWeight={600} mb={0.75}>
              Changed trace links <Typography component="span" variant="caption" color="text.secondary">(optional)</Typography>
            </Typography>
            <ToggleButtonGroup
              size="small"
              value={traceMode}
              exclusive
              onChange={(_, value: JsonInputMode | null) => {
                if (value) {
                  setTraceMode(value);
                  if (value === 'paste') { setTraceFilename(''); setTraceJson(TRACE_SAMPLE); }
                }
              }}
              sx={{ mb: 1 }}
            >
              <ToggleButton value="paste">Paste JSON</ToggleButton>
              <ToggleButton value="upload">Upload .json</ToggleButton>
            </ToggleButtonGroup>
            {traceMode === 'paste' ? (
              <TextField
                fullWidth
                multiline
                minRows={5}
                value={traceJson}
                onChange={(event) => setTraceJson(event.target.value)}
              />
            ) : (
              <FileUploadZone
                accept=".json"
                label="Upload changed trace links as a .json file"
                onFileContent={(content, filename) => { setTraceJson(content); setTraceFilename(filename); }}
                filename={traceFilename}
                onClear={() => { setTraceJson(''); setTraceFilename(''); }}
              />
            )}
          </Box>
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
            <ReviewQualityBand
              score={getReviewQualityScore(result.overall, result.requirement_set_findings)}
            />
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
                    <ReviewQualityBand
                      label="Requirement quality"
                      score={getReviewQualityScore(
                        reviewedRequirement.overall,
                        reviewedRequirement.findings
                      )}
                    />
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
