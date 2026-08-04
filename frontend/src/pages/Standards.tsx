import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { useStandards } from '@/hooks/useStandards';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Standards() {
  const { data, isLoading, isError, error } = useStandards();

  if (isLoading) return <LoadingSpinner message="Loading standards..." />;
  if (isError) {
    const message =
      (error as Error)?.message ||
      (error as { error?: { message?: string } })?.error?.message ||
      'Unable to reach the backend. Make sure the server is running.';
    return <Alert severity="error">Failed to load standards: {message}</Alert>;
  }

  const fromSharePoint = data?.source === 'sharepoint';

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={700}>
          Standards Library
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {fromSharePoint
            ? 'Reference documents pulled from SharePoint — used by deterministic reviewer engines.'
            : 'Versioned standards and references used by deterministic reviewer engines.'}
        </Typography>
        {fromSharePoint && (
          <Chip label="Live from SharePoint" color="primary" size="small" sx={{ mt: 0.75 }} />
        )}
      </Box>

      <Stack spacing={2}>
        {data?.standards.map((standard) => (
          <Paper key={standard.key} variant="outlined" sx={{ p: 2.5 }}>
            <Stack spacing={1}>
              <Box display="flex" justifyContent="space-between" alignItems="flex-start" gap={1} flexWrap="wrap">
                <Box flexGrow={1}>
                  <Typography variant="h6" fontWeight={700}>
                    {standard.name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Source: {standard.source}
                    {standard.last_modified && ` · Last modified: ${standard.last_modified}`}
                    {standard.file_size_bytes != null && ` · ${formatBytes(standard.file_size_bytes)}`}
                  </Typography>
                </Box>
                <Box display="flex" alignItems="center" gap={1} flexShrink={0}>
                  {standard.file_type && (
                    <Chip label={standard.file_type} size="small" variant="outlined" color="default" />
                  )}
                  <Chip label={`v${standard.version}`} size="small" />
                </Box>
              </Box>

              <Typography variant="body2">{standard.description}</Typography>

              <Box display="flex" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1}>
                <Box display="flex" gap={1} flexWrap="wrap">
                  {standard.categories.map((category) => (
                    <Chip key={`${standard.key}-${category}`} label={category} size="small" variant="outlined" />
                  ))}
                </Box>
                {standard.sharepoint_url && (
                  <Button
                    size="small"
                    variant="outlined"
                    endIcon={<OpenInNewIcon fontSize="small" />}
                    href={standard.sharepoint_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Open in SharePoint
                  </Button>
                )}
              </Box>
            </Stack>
          </Paper>
        ))}
      </Stack>
    </Stack>
  );
}

