import { useEffect, useMemo, useRef, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid2';
import MenuItem from '@mui/material/MenuItem';
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
import { ReviewResultHero } from '@/radia_ai/features/jamaRequirementReviewer/components/ReviewResultHero';
import { useRequirementReview } from '@/radia_ai/features/jamaRequirementReviewer/hooks/useRequirementReview';
import { useApplyFindingDisposition } from '@/radia_ai/features/jamaRequirementReviewer/hooks/useReviewHistory';
import { useNavigationGuard } from '@/hooks/useNavigationGuard';
import { useReviewCompleteSound } from '@/hooks/useReviewCompleteSound';
import { usePersistentState } from '@/hooks/usePersistentState';
import type { RequirementReviewResponse } from '@/types/api';
import { ErrorDisplay } from '@/components/ErrorDisplay';
import { normalizeRequirementLevel, REQUIREMENT_LEVELS } from '@/utils/requirementLevels';
import { normalizeRequirementText } from '@/radia_ai/features/jamaRequirementReviewer/utils/requirementNormalization';
import { getReviewQualityScore } from '@/utils/reviewQuality';
import { isReviewFailed } from '@/utils/reviewCompletion';
import { requirementReviewStyles } from './RequirementReview.styles';

type InputMode = 'paste' | 'upload';
type RequirementReviewFormState = {
  requirementId: string;
  requirementLevel: string;
  text: string;
  inputMode: InputMode;
  uploadedFilename: string;
};

const DEFAULT_FORM_STATE: RequirementReviewFormState = {
  requirementId: '',
  requirementLevel: 'Aircraft',
  text: '',
  inputMode: 'paste',
  uploadedFilename: '',
};

const DISPOSITION_SAVED_KEY = 'requirement-review-disposition-saved';

export default function RequirementReview() {
  const { state: formState, setState: setFormState, clear: clearFormState } = usePersistentState<RequirementReviewFormState>({
    key: 'requirement-review-form-state',
    initialValue: DEFAULT_FORM_STATE,
  });
  const { state: persistedResult, setState: setPersistedResult, clear: clearPersistedResult } = usePersistentState<RequirementReviewResponse | null>({
    key: 'requirement-review-result',
    initialValue: null,
  });
  const [requirementId, setRequirementId] = useState(formState.requirementId);
  const [requirementLevel, setRequirementLevel] = useState<string>(
    normalizeRequirementLevel(formState.requirementLevel)
  );
  const [text, setText] = useState(formState.text);
  const [inputMode, setInputMode] = useState<InputMode>(formState.inputMode);
  const [uploadedFilename, setUploadedFilename] = useState(formState.uploadedFilename);

  const {
    mutate: runReview,
    data: result,
    reset: resetResult,
    isPending,
    isError,
    error,
  } = useRequirementReview();
  const { mutate: applyDisposition, isPending: isApplyingDisposition } = useApplyFindingDisposition();
  const playReviewCompleteSound = useReviewCompleteSound();

  // On mount: if disposition was saved last time, clear all review data
  useEffect(() => {
    if (sessionStorage.getItem(DISPOSITION_SAVED_KEY) === 'true') {
      sessionStorage.removeItem(DISPOSITION_SAVED_KEY);
      clearFormState();
      clearPersistedResult();
      setRequirementId(DEFAULT_FORM_STATE.requirementId);
      setRequirementLevel(DEFAULT_FORM_STATE.requirementLevel);
      setText(DEFAULT_FORM_STATE.text);
      setInputMode(DEFAULT_FORM_STATE.inputMode);
      setUploadedFilename(DEFAULT_FORM_STATE.uploadedFilename);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const canSubmit = useMemo(() => text.trim().length > 0, [text]);
  const activeResult = result ?? persistedResult;
  const resultRef = useRef<HTMLDivElement | null>(null);

  const dispositionSavedThisSession = sessionStorage.getItem(DISPOSITION_SAVED_KEY) === 'true';

  // Guard navigation: dirty while input exists or result is unacknowledged.
  // Once the user saves a disposition, the result is considered acknowledged.
  const isDirty = (text.trim().length > 0 || !!activeResult || isPending) && !dispositionSavedThisSession;
  useNavigationGuard(isDirty);

  // Track isDirty in a ref so the unmount cleanup can read the latest value.
  const isDirtyRef = useRef(isDirty);
  useEffect(() => { isDirtyRef.current = isDirty; }, [isDirty]);

  // When the user discards (navigates away while dirty), clear persisted state
  // so returning to this page starts fresh instead of restoring stale data.
  useEffect(() => {
    return () => {
      if (isDirtyRef.current) {
        localStorage.removeItem('requirement-review-form-state');
        localStorage.removeItem('requirement-review-result');
        sessionStorage.removeItem(DISPOSITION_SAVED_KEY);
      }
    };
  }, []);

  const updateFormState = (next: Partial<RequirementReviewFormState>) => {
    setFormState((current) => ({ ...current, ...next }));
  };

  useEffect(() => {
    if (!activeResult) return;
    resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [activeResult]);

  const handleFileContent = (content: string, filename: string) => {
    const normalized = normalizeRequirementText(content);
    setText(normalized);
    setUploadedFilename(filename);
    updateFormState({ text: normalized, uploadedFilename: filename });
  };

  const handleClearFile = () => {
    setText('');
    setUploadedFilename('');
    updateFormState({ text: '', uploadedFilename: '' });
  };

  const handleClearAll = () => {
    clearFormState();
    clearPersistedResult();
    sessionStorage.removeItem(DISPOSITION_SAVED_KEY);
    setRequirementId(DEFAULT_FORM_STATE.requirementId);
    setRequirementLevel(DEFAULT_FORM_STATE.requirementLevel);
    setText(DEFAULT_FORM_STATE.text);
    setInputMode(DEFAULT_FORM_STATE.inputMode);
    setUploadedFilename(DEFAULT_FORM_STATE.uploadedFilename);
    resetResult();
  };

  const submitReview = () => {
    if (!text.trim()) return;
    runReview(
      {
        requirement_id: requirementId || undefined,
        requirement_level: requirementLevel,
        text: text.trim(),
      },
      {
        onSuccess: (response) => {
          setPersistedResult(response);
          // Don't signal "review complete" for a review that never ran.
          if (!isReviewFailed(response.completion)) {
            playReviewCompleteSound();
          }
        },
      }
    );
  };

  const reviewFailed = activeResult ? isReviewFailed(activeResult.completion) : false;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={700}>
          Individual Requirement Review
        </Typography>
        <Typography variant="body2" color="text.secondary">
          AI-powered review across language, structure, verifiability, traceability, and certification.
        </Typography>
      </Box>

      <Paper variant="outlined" sx={requirementReviewStyles.sectionPaper}>
        <Stack spacing={2}>
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 12, md: 4 }}>
              <TextField
                size="small"
                fullWidth
                label="Requirement ID"
                value={requirementId}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setRequirementId(nextValue);
                  updateFormState({ requirementId: nextValue });
                }}
                placeholder="REQ-1234"
              />
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <TextField
                select
                size="small"
                fullWidth
                label="Requirement Level"
                value={requirementLevel}
                onChange={(event) => {
                  const nextValue = normalizeRequirementLevel(event.target.value);
                  setRequirementLevel(nextValue);
                  updateFormState({ requirementLevel: nextValue });
                }}
              >
                {REQUIREMENT_LEVELS.map((level) => (
                  <MenuItem key={level} value={level}>
                    {level}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
          </Grid>

          <Box>
            <Typography variant="caption" color="text.secondary" sx={requirementReviewStyles.fieldLabel}>
              Requirement Text
            </Typography>
            <Box sx={requirementReviewStyles.inputModeRow}>
              <ToggleButtonGroup
                size="small"
                value={inputMode}
                exclusive
                onChange={(_, value: InputMode | null) => {
                  if (value) {
                    setInputMode(value);
                    updateFormState({ inputMode: value });
                    if (value === 'paste') {
                      setUploadedFilename('');
                      updateFormState({ uploadedFilename: '' });
                    }
                  }
                }}
              >
                <ToggleButton value="paste">Type / Paste</ToggleButton>
                <ToggleButton value="upload">Upload file</ToggleButton>
              </ToggleButtonGroup>
              <Button variant="outlined" color="inherit" onClick={handleClearAll}>
                Clear Review
              </Button>
            </Box>

            {inputMode === 'paste' ? (
              <TextField
                fullWidth
                multiline
                minRows={5}
                value={text}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setText(nextValue);
                  updateFormState({ text: nextValue });
                }}
                placeholder="The subsystem shall ..."
              />
            ) : (
              <FileUploadZone
                accept=".txt,.pdf"
                label="Upload a .pdf or .txt document containing the requirement"
                onFileContent={handleFileContent}
                filename={uploadedFilename}
                onClear={handleClearFile}
              />
            )}
          </Box>

          {uploadedFilename && text.trim() && (
            <TextField
              fullWidth
              multiline
              minRows={4}
              maxRows={12}
              value={text}
              InputProps={{ readOnly: true }}
              label="Extracted text (sent to AI)"
              size="small"
              helperText="This is the cleaned text extracted from your file."
            />
          )}

          <Box sx={requirementReviewStyles.actionRow}>
            <Button variant="contained" disabled={!canSubmit || isPending} onClick={submitReview}>
              Run AI review
            </Button>
          </Box>
        </Stack>
      </Paper>

      {isError && (
        <ErrorDisplay error={error} context="Requirement Review" onRetry={submitReview} />
      )}

      {/*
        A failed review has no score, no categories and no findings — show why it
        did not run instead of a result that would read as a clean pass.
      */}
      {activeResult && reviewFailed && (
        <Stack spacing={2} ref={resultRef}>
          <ReviewIncompleteNotice
            completion={activeResult.completion}
            onRetry={submitReview}
            isRetrying={isPending}
          />
        </Stack>
      )}

      {activeResult && !reviewFailed && (
        <Stack spacing={2} ref={resultRef}>
          <ReviewResultHero
            title="Requirement score"
            score={getReviewQualityScore(activeResult.overall, activeResult.findings)}
            status={activeResult.overall}
            findings={activeResult.findings}
            reviewId={activeResult.review_id}
            metadata={[
              { label: 'Requirement ID', value: requirementId || 'Not provided' },
              { label: 'Level', value: requirementLevel },
            ]}
          />
          <Paper variant="outlined" sx={requirementReviewStyles.sectionPaper}>
            <Stack spacing={2}>
              <Box>
            <Typography variant="h6" fontWeight={800} gutterBottom>
              Category scoring
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Individual sub-category quality scoring helps you spot where the requirement is weakest.
            </Typography>
              </Box>
              <CategoryScoreGrid categories={activeResult.category_results} reviewCompleted />
              <Divider />
              <ReviewChangeSet
                findings={activeResult.findings}
                reviewId={activeResult.review_id}
                onApplyDisposition={(reviewId, payload) => {
                  sessionStorage.setItem(DISPOSITION_SAVED_KEY, 'true');
                  applyDisposition({ reviewId, payload });
                }}
                isApplyingDisposition={isApplyingDisposition}
              />
            </Stack>
          </Paper>
        </Stack>
      )}
    </Stack>
  );
}
