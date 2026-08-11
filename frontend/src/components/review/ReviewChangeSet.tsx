import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import LinkIcon from '@mui/icons-material/Link';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Link from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { ReviewFinding } from '@/types/api';

interface ReviewChangeSetProps {
  findings: ReviewFinding[];
  title?: string;
  description?: string;
}

export function ReviewChangeSet({
  findings,
  title = 'AI change set',
  description = 'Proposed updates generated from review findings with direct links to the source standard.',
}: ReviewChangeSetProps) {
  if (findings.length === 0) {
    return <Alert severity="success">No changes were proposed for this review.</Alert>;
  }

  return (
    <Stack spacing={1.25}>
      <Box>
        <Typography variant="h6" fontWeight={800} gutterBottom>
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {description}
        </Typography>
      </Box>

      {findings.map((finding, index) => (
        <Paper key={`${finding.category}-${index}`} variant="outlined" sx={{ p: 1.5, borderRadius: 3 }}>
          <Stack spacing={1.25}>
            <Box display="flex" alignItems="center" justifyContent="space-between" gap={1} flexWrap="wrap">
              <Stack direction="row" spacing={1} alignItems="center">
                <AutoFixHighIcon color="primary" fontSize="small" />
                <Typography variant="subtitle2" fontWeight={800}>
                  Change {index + 1}
                </Typography>
              </Stack>
              <Stack direction="row" spacing={1} flexWrap="wrap">
                <Chip label={finding.category} size="small" variant="outlined" />
                <Chip label={finding.severity} size="small" />
              </Stack>
            </Box>

            <Box
              sx={{
                p: 1.25,
                borderRadius: 2,
                bgcolor: 'action.hover',
              }}
            >
              <Typography variant="overline" color="text.secondary">
                What was changed
              </Typography>
              <Typography variant="body2" mt={0.5}>
                {finding.recommendation}
              </Typography>
            </Box>

            <Box
              sx={{
                p: 1.25,
                borderRadius: 2,
                border: '1px dashed',
                borderColor: 'divider',
              }}
            >
              <Typography variant="overline" color="text.secondary">
                Current text basis
              </Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', mt: 0.5 }}>
                {finding.evidence}
              </Typography>
            </Box>

            <Box
              sx={{
                p: 1.25,
                borderRadius: 2,
                border: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Stack spacing={0.5}>
                <Typography variant="overline" color="text.secondary">
                  Source of truth
                </Typography>
                <Typography variant="body2" fontWeight={700}>
                  {finding.reference_title ?? finding.reference}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {finding.reference}
                </Typography>
                {finding.reference_url && (
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <LinkIcon fontSize="small" color="action" />
                    <Link href={finding.reference_url} target="_blank" rel="noopener noreferrer" underline="hover">
                      Open source standard
                    </Link>
                  </Stack>
                )}
              </Stack>
            </Box>
          </Stack>
        </Paper>
      ))}
    </Stack>
  );
}
