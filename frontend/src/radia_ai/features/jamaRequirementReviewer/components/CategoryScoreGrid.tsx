import Grid from '@mui/material/Grid2';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { CategoryResult, ReviewStatus } from '@/types/api';
import { getCategoryStatusScore, getReviewQualityColor } from '@/utils/reviewQuality';

interface CategoryScoreGridProps {
  categories: CategoryResult[];
}

const CATEGORY_LABEL_MAP: Record<string, string> = {
  language: 'Language',
  structure: 'Structure',
  verifiability: 'Verifiability',
  certification: 'Certification',
};

/**
 * The categories every completed review scores, in presentation order.
 *
 * The grid always renders these, so a category can never silently vanish from
 * the scorecard because a payload omitted it.
 */
const SCORED_CATEGORIES = ['language', 'structure', 'verifiability', 'certification'];

function toCategoryKey(value: string): string {
  return value.trim().toLowerCase();
}

function toDisplayLabel(value: string): string {
  const mapped = CATEGORY_LABEL_MAP[toCategoryKey(value)];
  if (mapped) return mapped;
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(' ');
}

type DisplayCategory = {
  key: string;
  label: string;
  /** Undefined when the payload carried no score for this category. */
  status?: ReviewStatus;
};

export function CategoryScoreGrid({ categories }: CategoryScoreGridProps) {
  const reported = new Map<string, ReviewStatus>();
  for (const item of categories) {
    reported.set(toCategoryKey(item.category), item.status);
  }

  const displayCategories: DisplayCategory[] = SCORED_CATEGORIES.map((key) => ({
    key,
    label: CATEGORY_LABEL_MAP[key],
    status: reported.get(key),
  }));

  // Surface anything the backend scored outside the standard set rather than hiding it.
  for (const item of categories) {
    const key = toCategoryKey(item.category);
    if (!SCORED_CATEGORIES.includes(key)) {
      displayCategories.push({ key, label: toDisplayLabel(item.category), status: item.status });
    }
  }

  return (
    <Grid container spacing={1} columns={displayCategories.length}>
      {displayCategories.map((category) => {
        // No status, or an explicitly unevaluated one, carries no score. Show a
        // placeholder rather than inventing a passing value.
        const score =
          category.status && category.status !== 'Not Evaluated'
            ? getCategoryStatusScore(category.status)
            : null;
        return (
          <Grid key={category.key} size={{ xs: displayCategories.length, sm: 1 }}>
            <Paper
              variant="outlined"
              sx={{
                p: 1,
                borderRadius: 2,
                borderColor: score == null ? 'divider' : `${getReviewQualityColor(score)}55`,
                background:
                  'linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.00))',
              }}
            >
              <Stack spacing={0.25}>
                <Typography variant="overline" color="text.secondary" sx={{ lineHeight: 1.2, fontSize: '0.6rem' }}>
                  {category.label}
                </Typography>
                <Typography variant="h6" fontWeight={800}>
                  {score == null ? '—' : score.toFixed(1)}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem' }}>
                  {category.status ?? 'Not scored'}
                </Typography>
              </Stack>
            </Paper>
          </Grid>
        );
      })}
    </Grid>
  );
}
