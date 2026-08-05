import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { getReviewQualityColor } from '@/utils/reviewQuality';

interface ReviewQualityBandProps {
  score: number;
  label?: string;
}

export function ReviewQualityBand({ score, label = 'Review quality' }: ReviewQualityBandProps) {
  const color = getReviewQualityColor(score);
  const position = `${Math.max(0, Math.min(100, (score / 10) * 100))}%`;

  return (
    <Stack spacing={0.5}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Box
        sx={{
          position: 'relative',
          height: 10,
          borderRadius: 999,
          background: 'linear-gradient(90deg, #dc2626 0%, #f59e0b 50%, #16a34a 100%)',
          overflow: 'hidden',
          boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.08)',
        }}
        aria-hidden="true"
      >
        <Box
          sx={{
            position: 'absolute',
            inset: 1,
            width: position,
            borderRadius: 999,
            background: 'rgba(255,255,255,0.12)',
          }}
        />
        <Box
          sx={{
            position: 'absolute',
            left: position,
            top: '50%',
            width: 14,
            height: 14,
            borderRadius: '50%',
            transform: 'translate(-50%, -50%)',
            bgcolor: color,
            border: '2px solid',
            borderColor: 'background.paper',
            boxShadow: '0 0 0 2px rgba(0,0,0,0.08)',
          }}
        />
      </Box>
    </Stack>
  );
}
