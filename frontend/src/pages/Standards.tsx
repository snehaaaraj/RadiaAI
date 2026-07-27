import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { useStandards } from '@/hooks/useStandards';

export default function Standards() {
  const { data, isLoading, isError, error } = useStandards();

  if (isLoading) return <LoadingSpinner message="Loading standards..." />;
  if (isError) return <Alert severity="error">Failed to load standards: {(error as Error).message}</Alert>;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={700}>
          Standards Library
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Versioned standards and references used by deterministic reviewer engines.
        </Typography>
      </Box>

      <Stack spacing={2}>
        {data?.standards.map((standard) => (
          <Paper key={standard.key} variant="outlined" sx={{ p: 2.5 }}>
            <Stack spacing={1}>
              <Box display="flex" justifyContent="space-between" alignItems="center" gap={1} flexWrap="wrap">
                <Typography variant="h6" fontWeight={700}>
                  {standard.name}
                </Typography>
                <Chip label={`v${standard.version}`} size="small" />
              </Box>
              <Typography variant="body2" color="text.secondary">
                Source: {standard.source}
              </Typography>
              <Typography variant="body2">{standard.description}</Typography>
              <Box display="flex" gap={1} flexWrap="wrap">
                {standard.categories.map((category) => (
                  <Chip key={`${standard.key}-${category}`} label={category} size="small" variant="outlined" />
                ))}
              </Box>
            </Stack>
          </Paper>
        ))}
      </Stack>
    </Stack>
  );
}

