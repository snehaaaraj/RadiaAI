import { useMemo, useState, useCallback, useEffect, useRef } from 'react';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid2';
import IconButton from '@mui/material/IconButton';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import { CategoryScoreGrid } from '@/components/review/CategoryScoreGrid';
import { FileUploadZone } from '@/components/review/FileUploadZone';
import { FindingCard } from '@/components/review/FindingCard';
import { ReviewResultHero } from '@/components/review/ReviewResultHero';
import { useApplyFindingDisposition } from '@/hooks/useReviewHistory';
import { usePersistentState } from '@/hooks/usePersistentState';
import { useRequirementSetReview } from '@/hooks/useRequirementSetReview';
import type { RequirementReviewInput, RequirementSetReviewResponse } from '@/types/api';
import { normalizeRequirementLevel, REQUIREMENT_LEVELS } from '@/utils/requirementLevels';
import { getReviewQualityScore } from '@/utils/reviewQuality';

interface RequirementDraft {
  requirement_id: string;
  requirement_level: string;
  text: string;
  parent_id: string;
  verification_method: string;
}

function toApiRequirement(draft: RequirementDraft): RequirementReviewInput {
  return {
    requirement_id: draft.requirement_id || undefined,
    requirement_level: draft.requirement_level,
    text: draft.text.trim(),
    metadata: {
      parent_id: draft.parent_id,
      verification_method: draft.verification_method,
    },
  };
}

function createEmptyDraft(): RequirementDraft {
  return {
    requirement_id: '',
    requirement_level: 'System',
    text: '',
    parent_id: '',
    verification_method: '',
  };
}

/** Parse a JSON array of requirement objects from an uploaded file. */
function parseJsonRequirements(content: string): RequirementDraft[] {
  const parsed = JSON.parse(content) as unknown[];
  if (!Array.isArray(parsed)) throw new Error('JSON file must contain an array of requirements.');
  return parsed.map((item) => {
    const record = item as Record<string, unknown>;
    const metadata = (record['metadata'] as Record<string, unknown> | undefined) ?? {};
    return {
      requirement_id: String(record['requirement_id'] ?? record['id'] ?? ''),
      requirement_level: normalizeRequirementLevel(
        String(record['requirement_level'] ?? record['level'] ?? 'System')
      ),
      text: String(record['text'] ?? record['requirement_text'] ?? record['description'] ?? ''),
      parent_id: String(metadata['parent_id'] ?? record['parent_id'] ?? ''),
      verification_method: String(
        metadata['verification_method'] ?? record['verification_method'] ?? ''
      ),
    };
  });
}

/** Parse a CSV file with header row into requirement drafts.
 *  Expected columns (order flexible): requirement_id, requirement_level, text,
 *  parent_id, verification_method. Extra columns are ignored.
 */
function parseCsvRequirements(content: string): RequirementDraft[] {
  const lines = content.split(/\r?\n/).filter((line) => line.trim());
  if (lines.length < 2) throw new Error('CSV must have a header row and at least one data row.');
  const headers = lines[0].split(',').map((h) => h.trim().toLowerCase().replace(/\s+/g, '_'));
  const col = (name: string) => headers.indexOf(name);
  const cell = (row: string[], idx: number) => (idx >= 0 ? (row[idx] ?? '').trim() : '');
  return lines.slice(1).map((line) => {
    const row = line.split(',');
    return {
      requirement_id: cell(row, col('requirement_id')) || cell(row, col('id')),
      requirement_level: normalizeRequirementLevel(
        cell(row, col('requirement_level')) || cell(row, col('level')) || 'System'
      ),
      text: cell(row, col('text')) || cell(row, col('requirement_text')) || cell(row, col('description')),
      parent_id: cell(row, col('parent_id')),
      verification_method: cell(row, col('verification_method')),
    };
  });
}

type InputMode = 'manual' | 'upload';
type RequirementSetFormState = {
  specificationId: string;
  requirements: RequirementDraft[];
  inputMode: InputMode;
  uploadedFilename: string;
  parseError: string;
};

const DEFAULT_SET_FORM_STATE: RequirementSetFormState = {
  specificationId: 'SPEC-001',
  requirements: [createEmptyDraft(), createEmptyDraft()],
  inputMode: 'manual',
  uploadedFilename: '',
  parseError: '',
};

export default function RequirementSetReview() {
  const { state: formState, setState: setFormState, clear: clearFormState } = usePersistentState<RequirementSetFormState>({
    key: 'requirement-set-review-form-state',
    initialValue: DEFAULT_SET_FORM_STATE,
  });
  const { state: persistedResult, setState: setPersistedResult, clear: clearPersistedResult } = usePersistentState<RequirementSetReviewResponse | null>({
    key: 'requirement-set-review-result',
    initialValue: null,
  });
  const [specificationId, setSpecificationId] = useState(formState.specificationId);
  const [requirements, setRequirements] = useState<RequirementDraft[]>(
    formState.requirements.map((item) => ({
      ...item,
      requirement_level: normalizeRequirementLevel(item.requirement_level),
    }))
  );
  const [inputMode, setInputMode] = useState<InputMode>(formState.inputMode);
  const [uploadedFilename, setUploadedFilename] = useState(formState.uploadedFilename);
  const [parseError, setParseError] = useState(formState.parseError);

  const {
    mutate: runReview,
    data: result,
    reset: resetResult,
    isPending,
    isError,
    error,
  } = useRequirementSetReview();
  const { mutate: applyDisposition, isPending: isApplyingDisposition } = useApplyFindingDisposition();

  const canSubmit = useMemo(
    () => requirements.some((item) => item.text.trim().length > 0),
    [requirements]
  );
  const activeResult = result ?? persistedResult;
  const resultRef = useRef<HTMLDivElement | null>(null);

  const updateFormState = useCallback((next: Partial<RequirementSetFormState>) => {
    setFormState((current) => ({ ...current, ...next }));
  }, [setFormState]);

  useEffect(() => {
    if (!activeResult) return;
    resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [activeResult]);

  const handleFileContent = useCallback((content: string, filename: string) => {
    setParseError('');
    updateFormState({ parseError: '' });
    try {
      const isJson = filename.toLowerCase().endsWith('.json');
      const drafts = isJson ? parseJsonRequirements(content) : parseCsvRequirements(content);
      if (drafts.length === 0) throw new Error('No requirements found in the uploaded file.');
      setRequirements(drafts);
      setUploadedFilename(filename);
      updateFormState({ requirements: drafts, uploadedFilename: filename });
    } catch (parseException) {
      const message = (parseException as Error).message;
      setParseError(message);
      updateFormState({ parseError: message });
    }
  }, [updateFormState]);

  const handleClearFile = useCallback(() => {
    setUploadedFilename('');
    setParseError('');
    setRequirements([createEmptyDraft(), createEmptyDraft()]);
    updateFormState({
      uploadedFilename: '',
      parseError: '',
      requirements: [createEmptyDraft(), createEmptyDraft()],
    });
  }, [updateFormState]);

  const handleClearAll = useCallback(() => {
    clearFormState();
    clearPersistedResult();
    setSpecificationId(DEFAULT_SET_FORM_STATE.specificationId);
    setRequirements(DEFAULT_SET_FORM_STATE.requirements);
    setInputMode(DEFAULT_SET_FORM_STATE.inputMode);
    setUploadedFilename(DEFAULT_SET_FORM_STATE.uploadedFilename);
    setParseError(DEFAULT_SET_FORM_STATE.parseError);
    resetResult();
  }, [clearFormState, clearPersistedResult, resetResult]);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={700}>
          Requirement Set Review
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Default production workflow for duplicate, overlap, contradiction, and traceability checks.
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

          <Box>
            <Typography variant="caption" color="text.secondary" display="block" mb={0.75}>
              Requirements Input
            </Typography>
            <Box
              display="flex"
              alignItems="center"
              justifyContent="space-between"
              gap={1}
              flexWrap="wrap"
              mb={1.5}
            >
              <ToggleButtonGroup
                size="small"
                value={inputMode}
                exclusive
                onChange={(_, value: InputMode | null) => {
                  if (value) {
                    setInputMode(value);
                    updateFormState({ inputMode: value });
                    if (value === 'manual') {
                      setUploadedFilename('');
                      setParseError('');
                      updateFormState({ uploadedFilename: '', parseError: '' });
                    }
                  }
                }}
              >
                <ToggleButton value="manual">Enter manually</ToggleButton>
                <ToggleButton value="upload">Upload file</ToggleButton>
              </ToggleButtonGroup>
              <Button variant="outlined" color="inherit" onClick={handleClearAll}>
                Clear Review
              </Button>
            </Box>

            {inputMode === 'upload' && (
              <FileUploadZone
                accept=".json,.csv"
                label="Upload a .json or .csv file containing requirements"
                onFileContent={handleFileContent}
                filename={uploadedFilename}
                onClear={handleClearFile}
              />
            )}

            {parseError && (
              <Alert severity="error" sx={{ mt: 1 }}>
                {parseError}
              </Alert>
            )}

            {uploadedFilename && !parseError && (
              <Alert severity="success" sx={{ mt: 1 }}>
                Loaded <strong>{requirements.length}</strong> requirement
                {requirements.length !== 1 ? 's' : ''} from <strong>{uploadedFilename}</strong>.
                Review or edit below before submitting.
              </Alert>
            )}
          </Box>

          {requirements.map((item, index) => (
            <Paper key={`requirement-${index}`} variant="outlined" sx={{ p: 2 }}>
              <Stack spacing={1.5}>
                <Box display="flex" alignItems="center" justifyContent="space-between">
                  <Typography variant="subtitle2" fontWeight={700}>
                    Requirement {index + 1}
                  </Typography>
                  <IconButton
                    size="small"
                    aria-label="remove requirement"
                    onClick={() =>
                      setRequirements((current) => {
                        const nextRequirements = current.filter((_, currentIndex) => currentIndex !== index);
                        updateFormState({ requirements: nextRequirements });
                        return nextRequirements;
                      })
                    }
                    disabled={requirements.length <= 1}
                  >
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                </Box>
                <Grid container spacing={1.5}>
                  <Grid size={{ xs: 12, md: 4 }}>
                    <TextField
                      size="small"
                      fullWidth
                      label="Requirement ID"
                      value={item.requirement_id}
                      onChange={(event) =>
                        setRequirements((current) => {
                          const nextRequirements = current.map((entry, entryIndex) =>
                            entryIndex === index ? { ...entry, requirement_id: event.target.value } : entry
                          );
                          updateFormState({ requirements: nextRequirements });
                          return nextRequirements;
                        })
                      }
                    />
                  </Grid>
                  <Grid size={{ xs: 12, md: 3 }}>
                    <TextField
                      select
                      size="small"
                      fullWidth
                      label="Requirement Level"
                      value={item.requirement_level}
                      onChange={(event) =>
                        setRequirements((current) => {
                          const nextRequirements = current.map((entry, entryIndex) =>
                            entryIndex === index
                              ? { ...entry, requirement_level: normalizeRequirementLevel(event.target.value) }
                              : entry
                          );
                          updateFormState({ requirements: nextRequirements });
                          return nextRequirements;
                        })
                      }
                    >
                      {REQUIREMENT_LEVELS.map((level) => (
                        <MenuItem key={level} value={level}>
                          {level}
                        </MenuItem>
                      ))}
                    </TextField>
                  </Grid>
                </Grid>
                <TextField
                  multiline
                  minRows={3}
                  label="Requirement Text"
                  value={item.text}
                  onChange={(event) =>
                    setRequirements((current) => {
                      const nextRequirements = current.map((entry, entryIndex) =>
                        entryIndex === index ? { ...entry, text: event.target.value } : entry
                      );
                      updateFormState({ requirements: nextRequirements });
                      return nextRequirements;
                    })
                  }
                />
                <TextField
                  size="small"
                  label="Parent Requirement ID"
                  value={item.parent_id}
                  onChange={(event) =>
                    setRequirements((current) => {
                      const nextRequirements = current.map((entry, entryIndex) =>
                        entryIndex === index ? { ...entry, parent_id: event.target.value } : entry
                      );
                      updateFormState({ requirements: nextRequirements });
                      return nextRequirements;
                    })
                  }
                />
                <TextField
                  size="small"
                  label="Verification Method"
                  value={item.verification_method}
                  onChange={(event) =>
                    setRequirements((current) => {
                      const nextRequirements = current.map((entry, entryIndex) =>
                        entryIndex === index
                          ? { ...entry, verification_method: event.target.value }
                          : entry
                      );
                      updateFormState({ requirements: nextRequirements });
                      return nextRequirements;
                    })
                  }
                  placeholder="test / analysis / inspection / demonstration"
                />
              </Stack>
            </Paper>
          ))}

          <Box display="flex" gap={1}>
            <Button
              variant="outlined"
              startIcon={<AddIcon />}
              onClick={() =>
                setRequirements((current) => {
                  const nextRequirements = [...current, createEmptyDraft()];
                  updateFormState({ requirements: nextRequirements });
                  return nextRequirements;
                })
              }
            >
              Add requirement
            </Button>
            <Button
              variant="contained"
              disabled={!canSubmit || isPending}
              onClick={() =>
                runReview(
                  {
                    specification_id: specificationId || undefined,
                    requirements: requirements
                      .filter((item) => item.text.trim().length > 0)
                      .map(toApiRequirement),
                  },
                  {
                    onSuccess: (response) => {
                      setPersistedResult(response);
                    },
                  }
                )
              }
            >
              Run requirement-set review
            </Button>
          </Box>
        </Stack>
      </Paper>

      {isError && <Alert severity="error">Review failed: {(error as Error).message}</Alert>}

      {activeResult && (
        <Stack spacing={2} ref={resultRef}>
          <ReviewResultHero
            title="Requirement set score"
            score={getReviewQualityScore(activeResult.overall, activeResult.findings)}
            status={activeResult.overall}
            findings={activeResult.findings}
            reviewId={activeResult.review_id}
            metadata={[
              { label: 'Specification', value: specificationId || 'Not provided' },
              { label: 'Reviewed', value: activeResult.requirement_count },
            ]}
          />
          <Paper variant="outlined" sx={{ p: 2.5 }}>
            <Stack spacing={2}>
              <Box>
                <Typography variant="h6" fontWeight={800} gutterBottom>
                  Category scoring
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Compare sub-category quality across the full uploaded or manually entered requirement set.
                </Typography>
              </Box>
              <CategoryScoreGrid categories={activeResult.category_results} />
              <Divider />
              <Box>
                <Typography variant="h6" fontWeight={800} gutterBottom>
                  Suggested changes
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Each recommendation is grouped with the source text and standards reference that informed it.
                </Typography>
              </Box>
              <Stack spacing={1.5}>
                {activeResult.findings.length === 0 ? (
                  <Alert severity="success">No findings detected for this requirement set.</Alert>
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
        </Stack>
      )}
    </Stack>
  );
}
