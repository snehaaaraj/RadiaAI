import Grid from '@mui/material/Grid2';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { CategoryResult, ReviewStatus } from '@/types/api';
import { getCategoryStatusScore, getReviewQualityColor } from '@/utils/reviewQuality';

interface CategoryScoreGridProps {
  categories: CategoryResult[];
  expectedCategories?: string[];
}

const CATEGORY_LABEL_MAP: Record<string, string> = {
  language: 'Language',
  structure: 'Structure',
  verifiability: 'Verifiability',
  certification: 'Certification',
};

const CATEGORY_SORT_PRIORITY: Record<string, number> = {
  language: 0,
  structure: 1,
  verifiability: 2,
  certification: 3,
};

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
  status?: ReviewStatus;
};

export function CategoryScoreGrid({
  categories,
  expectedCategories = ['Language', 'Structure', 'Verifiability', 'Certification'],
}: CategoryScoreGridProps) {
  const merged = new Map<string, DisplayCategory>();

  for (const item of categories) {
    if (toCategoryKey(item.category) === 'traceability') {
      continue;
    }

    const key = toCategoryKey(toDisplayLabel(item.category));
    merged.set(key, {
      key,
      label: toDisplayLabel(item.category),
      status: item.status,
    });
  }

  for (const expected of expectedCategories) {
    const key = toCategoryKey(expected);
    if (!merged.has(key)) {
      merged.set(key, { key, label: expected });
    }
  }

  const displayCategories = Array.from(merged.values()).sort((left, right) => {
    const leftPriority = CATEGORY_SORT_PRIORITY[left.key] ?? 99;
    const rightPriority = CATEGORY_SORT_PRIORITY[right.key] ?? 99;
    if (leftPriority !== rightPriority) return leftPriority - rightPriority;
    return left.label.localeCompare(right.label);
  });

  return (
    <Grid container spacing={1} columns={displayCategories.length}>
      {displayCategories.map((category) => {
        // 'Not Evaluated' carries no score — show it the same as a missing category.
        const score =
          category.status && category.status !== 'Not Evaluated'
            ? getCategoryStatusScore(category.status)
            : null;
        return (
          <Grid key={`${category.key}-${category.status ?? 'missing'}`} size={{ xs: displayCategories.length, sm: 1 }}>
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
                  {category.status ?? 'Not evaluated'}
                </Typography>
              </Stack>
            </Paper>
          </Grid>
        );
      })}
    </Grid>
  );
}
