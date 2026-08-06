import Grid from '@mui/material/Grid2';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { CategoryResult } from '@/types/api';
import { getCategoryStatusScore, getReviewQualityColor } from '@/utils/reviewQuality';

interface CategoryScoreGridProps {
  categories: CategoryResult[];
}

export function CategoryScoreGrid({ categories }: CategoryScoreGridProps) {
  return (
    <Grid container spacing={1.5}>
      {categories.map((category) => {
        const score = getCategoryStatusScore(category.status);
        return (
          <Grid key={`${category.category}-${category.status}`} size={{ xs: 12, sm: 6, lg: 3 }}>
            <Paper
              variant="outlined"
              sx={{
                p: 1.5,
                borderRadius: 3,
                borderColor: `${getReviewQualityColor(score)}55`,
                background:
                  'linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.00))',
              }}
            >
              <Stack spacing={0.75}>
                <Typography variant="overline" color="text.secondary" sx={{ lineHeight: 1.2 }}>
                  {category.category}
                </Typography>
                <Typography variant="h5" fontWeight={800}>
                  {score.toFixed(1)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {category.status}
                </Typography>
              </Stack>
            </Paper>
          </Grid>
        );
      })}
    </Grid>
  );
}
