import { useEffect, useMemo, useRef, useState } from 'react';
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
import { CategoryScoreGrid } from '@/radia_ai/features/jamaRequirementReviewer/components/CategoryScoreGrid';
import { FileUploadZone } from '@/radia_ai/features/jamaRequirementReviewer/components/FileUploadZone';
import { ReviewChangeSet } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewChangeSet';
import { ReviewQualityBand } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewQualityBand';
import { ReviewResultHero } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewResultHero';
import { ReviewStatusChip } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewStatusChip';
import { useDeltaReview } from '@/radia_ai/features/jamaRequirementReviewer/hooks/useDeltaReview';
import { useNavigationGuard } from '@/hooks/useNavigationGuard';
import { useReviewCompleteSound } from '@/hooks/useReviewCompleteSound';
import { usePersistentState } from '@/hooks/usePersistentState';
import { useApplyFindingDisposition } from '@/radia_ai/features/jamaRequirementReviewer/hooks/useReviewHistory';
import type { DeltaReviewInput, DeltaReviewResponse } from '@/types/api';
import { getApiErrorMessage } from '@/utils/apiErrorMessage';
import { getReviewQualityScore } from '@/utils/reviewQuality';

const BASELINE_SAMPLE = JSON.stringify(
  [
    {
      requirement_id: 'REQ-001',
      text: 'The subsystem shall enable diagnostics within 2 seconds.',
      requirement_level: 'System',
      metadata: { parent_id: 'P-100', verification_method: 'test' },
    },
    {
      requirement_id: 'REQ-002',
      text: 'The subsystem shall provide telemetry every 1 second.',
      requirement_level: 'System',
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
      requirement_level: 'System',
      metadata: { parent_id: 'P-100', verification_method: 'test' },
    },
    {
      requirement_id: 'REQ-003',
      text: 'The subsystem shall provide built-in test under nominal conditions.',
      requirement_level: 'System',
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
type DeltaReviewFormState = {
  specificationId: string;
  baselineJson: string;
  updatedJson: string;
  traceJson: string;
  parseError: string;
  baselineMode: JsonInputMode;
  updatedMode: JsonInputMode;
  traceMode: JsonInputMode;
  baselineFilename: string;
  updatedFilename: string;
  traceFilename: string;
};

const DEFAULT_DELTA_FORM_STATE: DeltaReviewFormState = {
  specificationId: 'SPEC-DELTA-1',
  baselineJson: BASELINE_SAMPLE,
  updatedJson: UPDATED_SAMPLE,
  traceJson: TRACE_SAMPLE,
  parseError: '',
  baselineMode: 'paste',
  updatedMode: 'paste',
  traceMode: 'paste',
  baselineFilename: '',
  updatedFilename: '',
  traceFilename: '',
};

export default function DeltaReview() {
  const { state: formState, setState: setFormState, clear: clearFormState } = usePersistentState<DeltaReviewFormState>({
    key: 'delta-review-form-state',
    initialValue: DEFAULT_DELTA_FORM_STATE,
  });
  const { state: persistedResult, setState: setPersistedResult, clear: clearPersistedResult } = usePersistentState<DeltaReviewResponse | null>({
    key: 'delta-review-result',
    initialValue: null,
  });
  const [specificationId, setSpecificationId] = useState(formState.specificationId);
  const [baselineJson, setBaselineJson] = useState(formState.baselineJson);
  const [updatedJson, setUpdatedJson] = useState(formState.updatedJson);
  const [traceJson, setTraceJson] = useState(formState.traceJson);
  const [parseError, setParseError] = useState(formState.parseError);
  const [baselineMode, setBaselineMode] = useState<JsonInputMode>(formState.baselineMode);
  const [updatedMode, setUpdatedMode] = useState<JsonInputMode>(formState.updatedMode);
  const [traceMode, setTraceMode] = useState<JsonInputMode>(formState.traceMode);
  const [baselineFilename, setBaselineFilename] = useState(formState.baselineFilename);
  const [updatedFilename, setUpdatedFilename] = useState(formState.updatedFilename);
  const [traceFilename, setTraceFilename] = useState(formState.traceFilename);

  const {
    mutate: runDeltaReview,
    data: result,
    reset: resetResult,
    isPending,
    isError,
    error,
  } = useDeltaReview();
  const { mutate: applyDisposition, isPending: isApplyingDisposition } = useApplyFindingDisposition();
  const playReviewCompleteSound = useReviewCompleteSound();

  const DISPOSITION_SAVED_KEY = 'delta-review-disposition-saved';

  // On mount: if disposition was saved last time, clear all review data
  useEffect(() => {
    if (sessionStorage.getItem(DISPOSITION_SAVED_KEY) === 'true') {
      sessionStorage.removeItem(DISPOSITION_SAVED_KEY);
      clearFormState();
      clearPersistedResult();
      setSpecificationId(DEFAULT_DELTA_FORM_STATE.specificationId);
      setBaselineJson(DEFAULT_DELTA_FORM_STATE.baselineJson);
      setUpdatedJson(DEFAULT_DELTA_FORM_STATE.updatedJson);
      setTraceJson(DEFAULT_DELTA_FORM_STATE.traceJson);
      setParseError(DEFAULT_DELTA_FORM_STATE.parseError);
      setBaselineMode(DEFAULT_DELTA_FORM_STATE.baselineMode);
      setUpdatedMode(DEFAULT_DELTA_FORM_STATE.updatedMode);
      setTraceMode(DEFAULT_DELTA_FORM_STATE.traceMode);
      setBaselineFilename(DEFAULT_DELTA_FORM_STATE.baselineFilename);
      setUpdatedFilename(DEFAULT_DELTA_FORM_STATE.updatedFilename);
      setTraceFilename(DEFAULT_DELTA_FORM_STATE.traceFilename);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const canSubmit = useMemo(() => baselineJson.trim() && updatedJson.trim(), [baselineJson, updatedJson]);
  const activeResult = result ?? persistedResult;
  const resultRef = useRef<HTMLDivElement | null>(null);

  const dispositionSavedThisSession = sessionStorage.getItem(DISPOSITION_SAVED_KEY) === 'true';

  // Guard navigation: dirty while input is changed or result is unacknowledged.
  // Once the user saves a disposition, the result is considered acknowledged.
  const isDirty = (
    baselineJson !== DEFAULT_DELTA_FORM_STATE.baselineJson ||
    updatedJson !== DEFAULT_DELTA_FORM_STATE.updatedJson ||
    traceJson !== DEFAULT_DELTA_FORM_STATE.traceJson ||
    specificationId !== DEFAULT_DELTA_FORM_STATE.specificationId ||
    !!activeResult ||
    isPending
  ) && !dispositionSavedThisSession;
  useNavigationGuard(isDirty);

  // Track isDirty in a ref so the unmount cleanup can read the latest value.
  const isDirtyRef = useRef(isDirty);
  useEffect(() => { isDirtyRef.current = isDirty; }, [isDirty]);

  // When the user discards (navigates away while dirty), clear persisted state
  // so returning to this page starts fresh instead of restoring stale data.
  useEffect(() => {
    return () => {
      if (isDirtyRef.current) {
        localStorage.removeItem('delta-review-form-state');
        localStorage.removeItem('delta-review-result');
        sessionStorage.removeItem(DISPOSITION_SAVED_KEY);
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateFormState = (next: Partial<DeltaReviewFormState>) => {
    setFormState((current) => ({ ...current, ...next }));
  };

  useEffect(() => {
    if (!activeResult) return;
    resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [activeResult]);

  const handleClearAll = () => {
    clearFormState();
    clearPersistedResult();
    sessionStorage.removeItem(DISPOSITION_SAVED_KEY);
    setSpecificationId(DEFAULT_DELTA_FORM_STATE.specificationId);
    setBaselineJson(DEFAULT_DELTA_FORM_STATE.baselineJson);
    setUpdatedJson(DEFAULT_DELTA_FORM_STATE.updatedJson);
    setTraceJson(DEFAULT_DELTA_FORM_STATE.traceJson);
    setParseError(DEFAULT_DELTA_FORM_STATE.parseError);
    setBaselineMode(DEFAULT_DELTA_FORM_STATE.baselineMode);
    setUpdatedMode(DEFAULT_DELTA_FORM_STATE.updatedMode);
    setTraceMode(DEFAULT_DELTA_FORM_STATE.traceMode);
    setBaselineFilename(DEFAULT_DELTA_FORM_STATE.baselineFilename);
    setUpdatedFilename(DEFAULT_DELTA_FORM_STATE.updatedFilename);
    setTraceFilename(DEFAULT_DELTA_FORM_STATE.traceFilename);
    resetResult();
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={700}>
          Delta Review
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Incremental AI-powered review for changed requirements only.
        </Typography>
      </Box>

      <Paper variant="outlined" sx={{ p: 2.5 }}>
        <Stack spacing={2}>
          <TextField
            size="small"
            label="Specification ID"
            value={specificationId}
            onChange={(event) => {
              const nextValue = event.target.value;
              setSpecificationId(nextValue);
              updateFormState({ specificationId: nextValue });
            }}
          />

          {/* Baseline */}
          <Box>
            <Typography variant="subtitle2" fontWeight={600} mb={0.75}>
              Baseline requirements
            </Typography>
            <Box
              display="flex"
              alignItems="center"
              justifyContent="space-between"
              gap={1}
              flexWrap="wrap"
              mb={1}
            >
              <ToggleButtonGroup
                size="small"
                value={baselineMode}
                exclusive
                onChange={(_, value: JsonInputMode | null) => {
                  if (value) {
                    setBaselineMode(value);
                    updateFormState({ baselineMode: value });
                    if (value === 'paste') {
                      setBaselineFilename('');
                      setBaselineJson(BASELINE_SAMPLE);
                      updateFormState({ baselineFilename: '', baselineJson: BASELINE_SAMPLE });
                    }
                  }
                }}
              >
                <ToggleButton value="paste">Paste JSON</ToggleButton>
                <ToggleButton value="upload">Upload .json</ToggleButton>
              </ToggleButtonGroup>
              <Button variant="outlined" color="inherit" onClick={handleClearAll}>
                Clear Review
              </Button>
            </Box>
            {baselineMode === 'paste' ? (
              <TextField
                fullWidth
                multiline
                minRows={7}
                value={baselineJson}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setBaselineJson(nextValue);
                  updateFormState({ baselineJson: nextValue });
                }}
              />
            ) : (
              <FileUploadZone
                accept=".json"
                label="Upload baseline requirements as a .json file"
                onFileContent={(content, filename) => {
                  setBaselineJson(content);
                  setBaselineFilename(filename);
                  updateFormState({ baselineJson: content, baselineFilename: filename });
                }}
                filename={baselineFilename}
                onClear={() => {
                  setBaselineJson('');
                  setBaselineFilename('');
                  updateFormState({ baselineJson: '', baselineFilename: '' });
                }}
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
                  updateFormState({ updatedMode: value });
                  if (value === 'paste') {
                    setUpdatedFilename('');
                    setUpdatedJson(UPDATED_SAMPLE);
                    updateFormState({ updatedFilename: '', updatedJson: UPDATED_SAMPLE });
                  }
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
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setUpdatedJson(nextValue);
                  updateFormState({ updatedJson: nextValue });
                }}
              />
            ) : (
              <FileUploadZone
                accept=".json"
                label="Upload updated requirements as a .json file"
                onFileContent={(content, filename) => {
                  setUpdatedJson(content);
                  setUpdatedFilename(filename);
                  updateFormState({ updatedJson: content, updatedFilename: filename });
                }}
                filename={updatedFilename}
                onClear={() => {
                  setUpdatedJson('');
                  setUpdatedFilename('');
                  updateFormState({ updatedJson: '', updatedFilename: '' });
                }}
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
                  updateFormState({ traceMode: value });
                  if (value === 'paste') {
                    setTraceFilename('');
                    setTraceJson(TRACE_SAMPLE);
                    updateFormState({ traceFilename: '', traceJson: TRACE_SAMPLE });
                  }
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
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setTraceJson(nextValue);
                  updateFormState({ traceJson: nextValue });
                }}
              />
            ) : (
              <FileUploadZone
                accept=".json"
                label="Upload changed trace links as a .json file"
                onFileContent={(content, filename) => {
                  setTraceJson(content);
                  setTraceFilename(filename);
                  updateFormState({ traceJson: content, traceFilename: filename });
                }}
                filename={traceFilename}
                onClear={() => {
                  setTraceJson('');
                  setTraceFilename('');
                  updateFormState({ traceJson: '', traceFilename: '' });
                }}
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
                  updateFormState({ parseError: '' });
                  runDeltaReview(payload, {
                    onSuccess: (response) => {
                      setPersistedResult(response);
                      playReviewCompleteSound();
                    },
                  });
                } catch (parseException) {
                  const message = (parseException as Error).message;
                  setParseError(message);
                  updateFormState({ parseError: message });
                }
              }}
            >
              Run delta review
            </Button>
          </Box>
          {parseError && <Alert severity="error">Invalid JSON input: {parseError}</Alert>}
        </Stack>
      </Paper>

      {isError && <Alert severity="error">Delta review failed: {getApiErrorMessage(error)}</Alert>}

      {activeResult && (
        <Stack spacing={2} ref={resultRef}>
          <ReviewResultHero
            title="Delta review score"
            score={getReviewQualityScore(activeResult.overall, activeResult.reviewed_requirements.flatMap(r => r.findings))}
            status={activeResult.overall}
            findings={activeResult.reviewed_requirements.flatMap(r => r.findings)}
            reviewId={activeResult.review_id}
            metadata={[
              { label: 'Specification', value: specificationId || 'Not provided' },
              { label: 'Changed items', value: activeResult.reviewed_requirements.length },
            ]}
          />
          <Paper variant="outlined" sx={{ p: 2.5 }}>
            <Stack spacing={2}>
              <Box display="flex" gap={1} flexWrap="wrap">
                <Chip label={`New: ${activeResult.change_summary.new_requirement_ids.length}`} size="small" />
                <Chip
                  label={`Modified: ${activeResult.change_summary.modified_requirement_ids.length}`}
                  size="small"
                />
                <Chip label={`Deleted: ${activeResult.change_summary.deleted_requirement_ids.length}`} size="small" />
                <Chip
                  label={`Trace changes: ${activeResult.change_summary.changed_trace_link_requirement_ids.length}`}
                  size="small"
                />
              </Box>
              <Divider />
              <Typography variant="h6" fontWeight={800}>
                Changed requirement results
              </Typography>
              {activeResult.reviewed_requirements.length === 0 ? (
                <Alert severity="success">No changed requirements to review.</Alert>
              ) : (
                activeResult.reviewed_requirements.map((reviewedRequirement) => (
                  <Paper key={reviewedRequirement.requirement_id} variant="outlined" sx={{ p: 1.75, borderRadius: 3 }}>
                    <Stack spacing={1.5}>
                      <Box display="flex" justifyContent="space-between" alignItems="center" gap={1} flexWrap="wrap">
                        <Typography variant="h6" fontWeight={800}>
                          {reviewedRequirement.requirement_id}
                        </Typography>
                        <ReviewStatusChip status={reviewedRequirement.overall} />
                      </Box>
                      <ReviewQualityBand
                        label="Requirement score"
                        score={getReviewQualityScore(
                          reviewedRequirement.overall,
                          reviewedRequirement.findings
                        )}
                      />
                      <CategoryScoreGrid categories={reviewedRequirement.category_results} />
                      <ReviewChangeSet
                        findings={reviewedRequirement.findings}
                        reviewId={activeResult.review_id}
                        onApplyDisposition={(reviewId, payload) => {
                          sessionStorage.setItem(DISPOSITION_SAVED_KEY, 'true');
                          applyDisposition({ reviewId, payload });
                        }}
                        isApplyingDisposition={isApplyingDisposition}
                      />
                    </Stack>
                  </Paper>
                ))
              )}
            </Stack>
          </Paper>
        </Stack>
      )}
    </Stack>
  );
}
