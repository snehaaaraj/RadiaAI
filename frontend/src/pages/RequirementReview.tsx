import { useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import MenuItem from '@mui/material/MenuItem';
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
import { useRequirementReview } from '@/hooks/useRequirementReview';
import { useApplyFindingDisposition } from '@/hooks/useReviewHistory';
import { usePersistentState } from '@/hooks/usePersistentState';
import type { RequirementReviewResponse } from '@/types/api';
import { getReviewQualityScore } from '@/utils/reviewQuality';

const REQUIREMENT_LEVELS = ['aircraft', 'system', 'subsystem', 'component'] as const;

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
  requirementLevel: 'system',
  text: '',
  inputMode: 'paste',
  uploadedFilename: '',
};

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
  const [requirementLevel, setRequirementLevel] = useState<string>(formState.requirementLevel);
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

  const canSubmit = useMemo(() => text.trim().length > 0, [text]);
  const activeResult = result ?? persistedResult;

  const updateFormState = (next: Partial<RequirementReviewFormState>) => {
    setFormState((current) => ({ ...current, ...next }));
  };

  const handleFileContent = (content: string, filename: string) => {
    setText(content);
    setUploadedFilename(filename);
    updateFormState({ text: content, uploadedFilename: filename });
  };

  const handleClearFile = () => {
    setText('');
    setUploadedFilename('');
    updateFormState({ text: '', uploadedFilename: '' });
  };

  const handleClearAll = () => {
    clearFormState();
    clearPersistedResult();
    setRequirementId(DEFAULT_FORM_STATE.requirementId);
    setRequirementLevel(DEFAULT_FORM_STATE.requirementLevel);
    setText(DEFAULT_FORM_STATE.text);
    setInputMode(DEFAULT_FORM_STATE.inputMode);
    setUploadedFilename(DEFAULT_FORM_STATE.uploadedFilename);
    resetResult();
  };

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
            onChange={(event) => {
              const nextValue = event.target.value;
              setRequirementId(nextValue);
              updateFormState({ requirementId: nextValue });
            }}
            placeholder="REQ-1234"
          />
          <TextField
            select
            size="small"
            label="Requirement Level"
            value={requirementLevel}
            onChange={(event) => {
              const nextValue = event.target.value;
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

          <Box>
            <Typography variant="caption" color="text.secondary" display="block" mb={0.75}>
              Requirement Text
            </Typography>
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
              sx={{ mb: 1.5 }}
            >
              <ToggleButton value="paste">Type / Paste</ToggleButton>
              <ToggleButton value="upload">Upload file</ToggleButton>
            </ToggleButtonGroup>

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
                accept=".txt,.doc,.docx"
                label="Upload a .txt or Word document containing the requirement"
                onFileContent={handleFileContent}
                filename={uploadedFilename}
                onClear={handleClearFile}
              />
            )}
          </Box>

          {uploadedFilename && text.trim() && (
            <Alert severity="info" sx={{ py: 0.5 }}>
              Loaded from <strong>{uploadedFilename}</strong> — review the text above before submitting.
            </Alert>
          )}

          <Box>
            <Button
              variant="contained"
              disabled={!canSubmit || isPending}
              onClick={() =>
                runReview({
                  requirement_id: requirementId || undefined,
                  requirement_level: requirementLevel,
                  text: text.trim(),
                }, {
                  onSuccess: (response) => {
                    setPersistedResult(response);
                  },
                })
              }
            >
              Run deterministic review
            </Button>
            <Button variant="outlined" color="inherit" onClick={handleClearAll} sx={{ ml: 1 }}>
              Clear
            </Button>
          </Box>
        </Stack>
      </Paper>

      {isError && <Alert severity="error">Review failed: {(error as Error).message}</Alert>}

      {activeResult && (
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Stack spacing={2}>
            <Box display="flex" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1}>
              <Typography variant="h6" fontWeight={700}>
                Review Result
              </Typography>
              <ReviewStatusChip status={activeResult.overall} size="medium" />
            </Box>
            <ReviewQualityBand
              score={getReviewQualityScore(activeResult.overall, activeResult.findings)}
            />
            {activeResult.review_id && (
              <Typography variant="caption" color="text.secondary">
                Review ID: {activeResult.review_id}
              </Typography>
            )}
            <Box display="flex" gap={1} flexWrap="wrap">
              {activeResult.category_results.map((category) => (
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
              {activeResult.findings.length === 0 ? (
                <Alert severity="success">No findings. Requirement is acceptable.</Alert>
              ) : (
                activeResult.findings.map((finding, index) => (
                  <FindingCard
                    key={`${finding.category}-${index}`}
                    finding={finding}
                    index={index}
                    reviewId={activeResult.review_id}
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
