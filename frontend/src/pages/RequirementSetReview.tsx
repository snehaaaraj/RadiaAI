import { useMemo, useState } from 'react';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { FindingCard } from '@/components/review/FindingCard';
import { ReviewStatusChip } from '@/components/review/ReviewStatusChip';
import { useApplyFindingDisposition } from '@/hooks/useReviewHistory';
import { useRequirementSetReview } from '@/hooks/useRequirementSetReview';
import type { RequirementReviewInput } from '@/types/api';

interface RequirementDraft {
  requirement_id: string;
  requirement_level: string;
  text: string;
  parent_id: string;
  verification_method: string;
}

const REQUIREMENT_LEVELS = ['aircraft', 'system', 'subsystem', 'component'] as const;

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
    requirement_level: 'system',
    text: '',
    parent_id: '',
    verification_method: '',
  };
}

export default function RequirementSetReview() {
  const [specificationId, setSpecificationId] = useState('SPEC-001');
  const [requirements, setRequirements] = useState<RequirementDraft[]>([
    createEmptyDraft(),
    createEmptyDraft(),
  ]);

  const {
    mutate: runReview,
    data: result,
    isPending,
    isError,
    error,
  } = useRequirementSetReview();
  const { mutate: applyDisposition, isPending: isApplyingDisposition } = useApplyFindingDisposition();

  const canSubmit = useMemo(
    () => requirements.some((item) => item.text.trim().length > 0),
    [requirements]
  );

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
            onChange={(event) => setSpecificationId(event.target.value)}
          />

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
                      setRequirements((current) => current.filter((_, currentIndex) => currentIndex !== index))
                    }
                    disabled={requirements.length <= 1}
                  >
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                </Box>
                <TextField
                  size="small"
                  label="Requirement ID"
                  value={item.requirement_id}
                  onChange={(event) =>
                    setRequirements((current) =>
                      current.map((entry, entryIndex) =>
                        entryIndex === index ? { ...entry, requirement_id: event.target.value } : entry
                      )
                    )
                  }
                />
                <TextField
                  select
                  size="small"
                  label="Requirement Level"
                  value={item.requirement_level}
                  onChange={(event) =>
                    setRequirements((current) =>
                      current.map((entry, entryIndex) =>
                        entryIndex === index ? { ...entry, requirement_level: event.target.value } : entry
                      )
                    )
                  }
                >
                  {REQUIREMENT_LEVELS.map((level) => (
                    <MenuItem key={level} value={level}>
                      {level}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField
                  multiline
                  minRows={3}
                  label="Requirement Text"
                  value={item.text}
                  onChange={(event) =>
                    setRequirements((current) =>
                      current.map((entry, entryIndex) =>
                        entryIndex === index ? { ...entry, text: event.target.value } : entry
                      )
                    )
                  }
                />
                <TextField
                  size="small"
                  label="Parent Requirement ID"
                  value={item.parent_id}
                  onChange={(event) =>
                    setRequirements((current) =>
                      current.map((entry, entryIndex) =>
                        entryIndex === index ? { ...entry, parent_id: event.target.value } : entry
                      )
                    )
                  }
                />
                <TextField
                  size="small"
                  label="Verification Method"
                  value={item.verification_method}
                  onChange={(event) =>
                    setRequirements((current) =>
                      current.map((entry, entryIndex) =>
                        entryIndex === index
                          ? { ...entry, verification_method: event.target.value }
                          : entry
                      )
                    )
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
              onClick={() => setRequirements((current) => [...current, createEmptyDraft()])}
            >
              Add requirement
            </Button>
            <Button
              variant="contained"
              disabled={!canSubmit || isPending}
              onClick={() =>
                runReview({
                  specification_id: specificationId || undefined,
                  requirements: requirements
                    .filter((item) => item.text.trim().length > 0)
                    .map(toApiRequirement),
                })
              }
            >
              Run requirement-set review
            </Button>
          </Box>
        </Stack>
      </Paper>

      {isError && <Alert severity="error">Review failed: {(error as Error).message}</Alert>}

      {result && (
        <Paper variant="outlined" sx={{ p: 2.5 }}>
          <Stack spacing={2}>
            <Box display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
              <Typography variant="h6" fontWeight={700}>
                Requirement Set Result
              </Typography>
              <ReviewStatusChip status={result.overall} size="medium" />
            </Box>
            <Typography variant="body2" color="text.secondary">
              Reviewed requirements: {result.requirement_count}
            </Typography>
            {result.review_id && (
              <Typography variant="caption" color="text.secondary">
                Review ID: {result.review_id}
              </Typography>
            )}
            <Box display="flex" gap={1} flexWrap="wrap">
              {result.category_results.map((category) => (
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
              {result.findings.length === 0 ? (
                <Alert severity="success">No findings detected for this requirement set.</Alert>
              ) : (
                result.findings.map((finding, index) => (
                  <FindingCard
                    key={`${finding.category}-${index}`}
                    finding={finding}
                    index={index}
                    reviewId={result.review_id}
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
