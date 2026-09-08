import { useEffect, useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Autocomplete from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Link from '@mui/material/Link';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import {
  useJamaProjects,
  useJamaRequirement,
  useJamaRequirementSearch,
} from '@/radia_ai/features/jamaRequirementReviewer/hooks/useJama';
import type {
  ErrorResponse,
  JamaRequirement,
  JamaRequirementSummary,
} from '@/types/api';

interface JamaRequirementPickerProps {
  onRequirementSelected: (requirement: JamaRequirement) => void;
  disabled?: boolean;
}

function errorCode(error: unknown): string | undefined {
  return (error as ErrorResponse | undefined)?.error?.code;
}

function summaryLabel(summary: JamaRequirementSummary): string {
  const key = summary.document_key ?? `#${summary.id}`;
  return summary.name ? `${key} — ${summary.name}` : key;
}

export function JamaRequirementPicker({
  onRequirementSelected,
  disabled = false,
}: JamaRequirementPickerProps) {
  const [projectId, setProjectId] = useState<number | ''>('');
  const [inputValue, setInputValue] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const projectsQuery = useJamaProjects();

  // Debounce the free-text query so we don't call Jama on every keystroke.
  useEffect(() => {
    const handle = setTimeout(() => setDebouncedQuery(inputValue.trim()), 350);
    return () => clearTimeout(handle);
  }, [inputValue]);

  const searchEnabled = !disabled && (projectId !== '' || debouncedQuery.length >= 2);
  const searchQuery = useJamaRequirementSearch({
    projectId: projectId === '' ? undefined : projectId,
    contains: debouncedQuery || undefined,
    enabled: searchEnabled,
  });

  const requirementQuery = useJamaRequirement(selectedId);

  // When a full requirement finishes loading, hand it up to the parent form.
  useEffect(() => {
    if (requirementQuery.data) {
      onRequirementSelected(requirementQuery.data);
    }
    // onRequirementSelected is stable enough for this effect's purpose.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requirementQuery.data]);

  const options = useMemo(
    () => searchQuery.data?.results ?? [],
    [searchQuery.data]
  );

  const notConfigured = errorCode(projectsQuery.error) === 'JAMA_NOT_CONFIGURED';
  const searchError = searchQuery.isError && !notConfigured;

  if (notConfigured) {
    return (
      <Alert severity="info" variant="outlined">
        Jama is not connected. Ask an administrator to configure the Jama credentials on the
        server (JAMA_BASE_URL and API credentials) to browse requirements here.
      </Alert>
    );
  }

  return (
    <Stack spacing={1.5}>
      <TextField
        select
        size="small"
        fullWidth
        label="Jama project"
        value={projectId === '' ? '' : String(projectId)}
        onChange={(event) => {
          const value = event.target.value;
          setProjectId(value === '' ? '' : Number(value));
        }}
        disabled={disabled || projectsQuery.isLoading}
        helperText={
          projectsQuery.isError && !notConfigured
            ? 'Could not load projects from Jama.'
            : 'Optional — narrows the requirement search to one project.'
        }
      >
        <MenuItem value="">All projects</MenuItem>
        {(projectsQuery.data?.projects ?? []).map((project) => (
          <MenuItem key={project.id} value={String(project.id)}>
            {project.name}
            {project.project_key ? ` (${project.project_key})` : ''}
          </MenuItem>
        ))}
      </TextField>

      <Autocomplete<JamaRequirementSummary>
        fullWidth
        size="small"
        disabled={disabled}
        options={options}
        loading={searchQuery.isFetching}
        filterOptions={(x) => x}
        getOptionLabel={summaryLabel}
        isOptionEqualToValue={(option, value) => option.id === value.id}
        noOptionsText={
          debouncedQuery.length < 2 && projectId === ''
            ? 'Type at least 2 characters or pick a project'
            : 'No matching requirements'
        }
        onInputChange={(_, value, reason) => {
          if (reason === 'input') setInputValue(value);
        }}
        onChange={(_, value) => setSelectedId(value ? value.id : null)}
        renderInput={(params) => (
          <TextField
            {...params}
            label="Search Jama requirements"
            placeholder="Search by keyword or ID (e.g. braking, REQ-123)"
            InputProps={{
              ...params.InputProps,
              endAdornment: (
                <>
                  {searchQuery.isFetching ? <CircularProgress color="inherit" size={16} /> : null}
                  {params.InputProps.endAdornment}
                </>
              ),
            }}
          />
        )}
        renderOption={(props, option) => (
          <Box component="li" {...props} key={option.id}>
            <Stack>
              <Typography variant="body2" fontWeight={600}>
                {option.document_key ?? `#${option.id}`}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {option.name || 'Untitled requirement'}
              </Typography>
            </Stack>
          </Box>
        )}
      />

      {searchError && (
        <Alert severity="warning" variant="outlined">
          Could not search Jama requirements. Please try again.
        </Alert>
      )}

      {requirementQuery.isFetching && (
        <Stack direction="row" spacing={1} alignItems="center">
          <CircularProgress size={16} />
          <Typography variant="caption" color="text.secondary">
            Loading requirement from Jama…
          </Typography>
        </Stack>
      )}

      {requirementQuery.isError && (
        <Alert severity="warning" variant="outlined">
          Could not read the selected requirement from Jama.
        </Alert>
      )}

      {requirementQuery.data && (
        <Typography variant="caption" color="text.secondary">
          Loaded {requirementQuery.data.document_key ?? `#${requirementQuery.data.id}`}
          {requirementQuery.data.web_url ? (
            <>
              {' — '}
              <Link href={requirementQuery.data.web_url} target="_blank" rel="noreferrer">
                open in Jama
              </Link>
            </>
          ) : null}
        </Typography>
      )}
    </Stack>
  );
}
