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
import { ReviewIncompleteNotice } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewIncompleteNotice';
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
import { isReviewFailed, isReviewIncomplete } from '@/utils/reviewCompletion';

// Simple text format: one requirement per line (optional REQ-ID prefix)
const BASELINE_SAMPLE = `The flight control system shall maintain altitude within ±50 feet of the commanded altitude during cruise flight.
The telemetry system shall transmit position data to ground control at intervals not exceeding 1.0 seconds.`;

const UPDATED_SAMPLE = `The flight control system shall maintain altitude within ±25 feet of the commanded altitude during cruise flight under nominal conditions.
The diagnostic system shall execute a complete self-test sequence within 5.0 seconds of system power-on.`;

/**
 * Parse simple text format (one requirement per line) into RequirementReviewInput array.
 * Supported formats:
 * - requirement text
 * - REQ-ID: requirement text
 */
function parseRequirementsFromText(text: string): Array<{
  requirement_id?: string;
  text: string;
  requirement_level?: string;
  metadata?: Record<string, string>;
}> {
  const idPrefixedLinePattern = /^([A-Za-z0-9_.-]+):(.*)$/;

  return text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => {
      const prefixedMatch = line.match(idPrefixedLinePattern);
      const requirementId = prefixedMatch?.[1]?.trim();
      const requirementText = (prefixedMatch ? prefixedMatch[2] : line).trim();

      if (!requirementText) {
        throw new Error(`Missing requirement text in line: "${line}"`);
      }

      return {
        requirement_id: requirementId || undefined,
        text: requirementText,
        requirement_level: 'System',
        metadata: {},
      };
    });
}

type JsonInputMode = 'paste' | 'upload';
type DeltaReviewFormState = {
  specificationId: string;
  baselineJson: string;
  updatedJson: string;
  parseError: string;
  baselineMode: JsonInputMode;
  updatedMode: JsonInputMode;
  baselineFilename: string;
  updatedFilename: string;
};

const DEFAULT_DELTA_FORM_STATE: DeltaReviewFormState = {
  specificationId: 'SPEC-DELTA-1',
  baselineJson: BASELINE_SAMPLE,
  updatedJson: UPDATED_SAMPLE,
  parseError: '',
  baselineMode: 'paste',
  updatedMode: 'paste',
  baselineFilename: '',
  updatedFilename: '',
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
  const [parseError, setParseError] = useState(formState.parseError);
  const [baselineMode, setBaselineMode] = useState<JsonInputMode>(formState.baselineMode);
  const [updatedMode, setUpdatedMode] = useState<JsonInputMode>(formState.updatedMode);
  const [baselineFilename, setBaselineFilename] = useState(formState.baselineFilename);
  const [updatedFilename, setUpdatedFilename] = useState(formState.updatedFilename);

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
      setParseError(DEFAULT_DELTA_FORM_STATE.parseError);
      setBaselineMode(DEFAULT_DELTA_FORM_STATE.baselineMode);
      setUpdatedMode(DEFAULT_DELTA_FORM_STATE.updatedMode);
      setBaselineFilename(DEFAULT_DELTA_FORM_STATE.baselineFilename);
      setUpdatedFilename(DEFAULT_DELTA_FORM_STATE.updatedFilename);
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
    setParseError(DEFAULT_DELTA_FORM_STATE.parseError);
    setBaselineMode(DEFAULT_DELTA_FORM_STATE.baselineMode);
    setUpdatedMode(DEFAULT_DELTA_FORM_STATE.updatedMode);
    setBaselineFilename(DEFAULT_DELTA_FORM_STATE.baselineFilename);
    setUpdatedFilename(DEFAULT_DELTA_FORM_STATE.updatedFilename);
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
                <ToggleButton value="paste">Paste text</ToggleButton>
                <ToggleButton value="upload">Upload .txt</ToggleButton>
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
                placeholder="The system shall...&#10;The subsystem shall..."
                helperText="Enter one requirement per line. Optional format: REQ-ID: requirement text"
              />
            ) : (
              <FileUploadZone
                accept=".txt,.json"
                label="Upload baseline requirements as a .txt or .json file"
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
              <ToggleButton value="paste">Paste text</ToggleButton>
              <ToggleButton value="upload">Upload .txt</ToggleButton>
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
                placeholder="The system shall...&#10;The subsystem shall..."
                helperText="Enter one requirement per line. Optional format: REQ-ID: requirement text"
              />
            ) : (
              <FileUploadZone
                accept=".txt,.json"
                label="Upload updated requirements as a .txt or .json file"
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

          <Box>
            <Button
              variant="contained"
              disabled={!canSubmit || isPending}
              onClick={() => {
                try {
                  const payload: DeltaReviewInput = {
                    specification_id: specificationId || undefined,
                    baseline_requirements: parseRequirementsFromText(baselineJson),
                    updated_requirements: parseRequirementsFromText(updatedJson),
                  };
                  setParseError('');
                  updateFormState({ parseError: '' });
                  runDeltaReview(payload, {
                    onSuccess: (response) => {
                      setPersistedResult(response);
                      // Don't signal "review complete" for a run that never evaluated anything.
                      if (!isReviewFailed(response.completion)) {
                        playReviewCompleteSound();
                      }
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
          {parseError && <Alert severity="error">Invalid requirement input: {parseError}</Alert>}
        </Stack>
      </Paper>

      {isError && <Alert severity="error">Delta review failed: {getApiErrorMessage(error)}</Alert>}

      {/* Nothing was evaluated — explain why instead of showing an empty result. */}
      {activeResult && isReviewFailed(activeResult.completion) && (
        <Stack spacing={2} ref={resultRef}>
          <ReviewIncompleteNotice completion={activeResult.completion} />
        </Stack>
      )}

      {activeResult && !isReviewFailed(activeResult.completion) && (
        <Stack spacing={2} ref={resultRef}>
          {/* Some requirements were evaluated and some were not — say so up front. */}
          {isReviewIncomplete(activeResult.completion) && (
            <ReviewIncompleteNotice completion={activeResult.completion} />
          )}
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
              </Box>
              <Divider />
              <Typography variant="h6" fontWeight={800}>
                Changed requirement results
              </Typography>
              {activeResult.reviewed_requirements.length === 0 ? (
                <Alert severity="success">No changed requirements to review.</Alert>
              ) : (
                (() => {
                  // Build a map from requirement_id -> starting flattened finding index
                  const requirementToStartIndex: Record<string, number> = {};
                  let globalIndex = 0;
                  for (const req of activeResult.reviewed_requirements) {
                    requirementToStartIndex[req.requirement_id] = globalIndex;
                    globalIndex += req.findings.length;
                  }

                  return activeResult.reviewed_requirements.map((reviewedRequirement) => (
                    <Paper key={reviewedRequirement.requirement_id} variant="outlined" sx={{ p: 1.75, borderRadius: 3 }}>
                      <Stack spacing={1.5}>
                        <Box display="flex" justifyContent="space-between" alignItems="center" gap={1} flexWrap="wrap">
                          <Typography variant="h6" fontWeight={800}>
                            {reviewedRequirement.requirement_id}
                          </Typography>
                          <ReviewStatusChip status={reviewedRequirement.overall} />
                        </Box>
                        {isReviewFailed(reviewedRequirement.completion) ? (
                          <ReviewIncompleteNotice completion={reviewedRequirement.completion} />
                        ) : (
                          <>
                            <ReviewQualityBand
                              label="Requirement score"
                              score={getReviewQualityScore(
                                reviewedRequirement.overall,
                                reviewedRequirement.findings
                              )}
                            />
                            <CategoryScoreGrid categories={reviewedRequirement.category_results} reviewCompleted />
                            <ReviewChangeSet
                              findings={reviewedRequirement.findings}
                              reviewId={activeResult.review_id}
                              onApplyDisposition={(reviewId, payload) => {
                                // Translate per-requirement finding index to global flattened index
                                const startIndex = requirementToStartIndex[reviewedRequirement.requirement_id] ?? 0;
                                const globalFindingIndex = startIndex + payload.finding_index;
                                sessionStorage.setItem(DISPOSITION_SAVED_KEY, 'true');
                                applyDisposition({
                                  reviewId,
                                  payload: { ...payload, finding_index: globalFindingIndex },
                                });
                              }}
                              isApplyingDisposition={isApplyingDisposition}
                            />
                          </>
                        )}
                      </Stack>
                    </Paper>
                  ));
                })()
              )}
            </Stack>
          </Paper>
        </Stack>
      )}
    </Stack>
  );
}
