import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Grid from '@mui/material/Grid2';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { FindingSeverity, ReviewFinding, ReviewStatus } from '@/types/api';
import { ReviewQualityBand } from './ReviewQualityBand';
import { ReviewStatusChip } from './ReviewStatusChip';

const SEVERITIES: FindingSeverity[] = ['Critical', 'High', 'Medium', 'Low'];

interface ReviewResultHeroProps {
  title: string;
  score: number;
  status: ReviewStatus;
  findings: ReviewFinding[];
  reviewId?: string | null;
  metadata?: Array<{ label: string; value: string | number }>;
}

export function ReviewResultHero({
  title,
  score,
  status,
  findings,
  reviewId,
  metadata = [],
}: ReviewResultHeroProps) {
  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        borderRadius: 4,
        background:
          'linear-gradient(135deg, rgba(27,79,216,0.10), rgba(107,33,168,0.08) 45%, rgba(15,23,42,0.02))',
      }}
    >
      <Grid container spacing={2} alignItems="stretch">
        <Grid size={{ xs: 12, md: 7 }}>
          <Stack spacing={1.25} justifyContent="space-between" height="100%">
            <Box display="flex" alignItems="center" justifyContent="space-between" gap={1} flexWrap="wrap">
              <Typography variant="h5" fontWeight={800}>
                {title}
              </Typography>
              <ReviewStatusChip status={status} size="medium" />
            </Box>
            <Typography variant="body2" color="text.secondary">
              Review outcome is highlighted below with category-level scoring and evidence-backed
              recommendations.
            </Typography>
            <ReviewQualityBand score={score} label="Overall score" showValue={false} />
            <Stack direction="row" gap={1} flexWrap="wrap">
              {metadata.map((item) => (
                <Chip key={item.label} label={`${item.label}: ${item.value}`} variant="outlined" size="small" />
              ))}
              {reviewId && <Chip label={`Review ID: ${reviewId}`} variant="outlined" size="small" />}
            </Stack>
          </Stack>
        </Grid>
        <Grid size={{ xs: 12, md: 5 }}>
          <Stack spacing={1}>
            {findings.length === 0 ? (
              <Alert severity="success">No findings were detected for this review.</Alert>
            ) : (
              <>
                <Typography variant="subtitle2" fontWeight={700}>
                  Finding intensity
                </Typography>
                <Stack direction="row" gap={1} flexWrap="wrap">
                  {SEVERITIES.map((severity) => {
                    const count = findings.filter((finding) => finding.severity === severity).length;
                    if (count === 0) return null;
                    return <Chip key={severity} label={`${severity}: ${count}`} size="small" />;
                  })}
                </Stack>
                <Typography variant="caption" color="text.secondary">
                  {findings.length} total finding{findings.length === 1 ? '' : 's'} surfaced.
                </Typography>
              </>
            )}
          </Stack>
        </Grid>
      </Grid>
    </Paper>
  );
}
