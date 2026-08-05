import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid2';
import RuleIcon from '@mui/icons-material/Rule';
import PlaylistAddCheckIcon from '@mui/icons-material/PlaylistAddCheck';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { useNavigate } from 'react-router-dom';
import { useHealth } from '@/hooks/useHealth';
import { ROUTES } from '@/utils/constants';

const QUICK_ACTIONS = [
  {
    title: 'Requirement Set Review',
    description: 'Review an entire specification for duplicates, overlaps, contradictions, and traceability gaps.',
    icon: <PlaylistAddCheckIcon color="primary" />,
    path: ROUTES.REVIEW_REQUIREMENT_SET,
    label: 'Open set review',
  },
  {
    title: 'Single Requirement Review',
    description: 'Check one requirement for language, structure, and verifiability.',
    icon: <RuleIcon color="secondary" />,
    path: ROUTES.REVIEW_REQUIREMENT,
    label: 'Open single review',
  },
  {
    title: 'Delta Review',
    description: 'Review only the items that changed between revisions.',
    icon: <CompareArrowsIcon sx={{ color: 'warning.main' }} />,
    path: ROUTES.REVIEW_DELTA,
    label: 'Open delta review',
  },
] as const;

export default function Home() {
  const navigate = useNavigate();
  const { data: health, isLoading } = useHealth();

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" gutterBottom fontWeight={700}>
          Requirements Engineering Assistant
        </Typography>
        <Typography variant="body1" color="text.secondary" maxWidth={720}>
          Deterministic review workflows for requirement quality, traceability, and revision control.
        </Typography>
      </Box>

      <Card>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="space-between" gap={2} flexWrap="wrap">
            <Box>
              <Typography variant="subtitle2" color="text.secondary">
                System status
              </Typography>
              <Box mt={1}>
                {isLoading ? (
                  <Chip label="Checking..." size="small" />
                ) : (
                  <Chip
                    icon={<CheckCircleIcon />}
                    label={`API ${health?.status ?? 'unknown'} — v${health?.version ?? '—'}`}
                    color={health?.status === 'ok' ? 'success' : 'warning'}
                    size="small"
                    variant="outlined"
                  />
                )}
              </Box>
            </Box>
            <Box display="flex" gap={1} flexWrap="wrap">
              <Chip label="Deterministic" variant="outlined" />
              <Chip label="Explainable" variant="outlined" />
              <Chip label="Traceable" variant="outlined" />
            </Box>
          </Box>
        </CardContent>
      </Card>

      <Grid container spacing={2}>
        {QUICK_ACTIONS.map(({ title, description, icon, path, label }) => (
          <Grid key={path} size={{ xs: 12, md: 4 }}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Box mb={1.5}>{icon}</Box>
                <Typography variant="h6" gutterBottom fontWeight={700}>
                  {title}
                </Typography>
                <Typography variant="body2" color="text.secondary" mb={2}>
                  {description}
                </Typography>
                <Button variant="outlined" size="small" onClick={() => navigate(path)}>
                  {label}
                </Button>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Card>
        <CardContent>
          <Typography variant="h6" fontWeight={700} gutterBottom>
            What this app does
          </Typography>
          <Typography variant="body2" color="text.secondary">
            It supports single requirement review, set review, delta review, review history, and
            standards references for aerospace requirements engineering.
          </Typography>
          <Divider sx={{ my: 2 }} />
          <Box display="flex" gap={1} flexWrap="wrap">
            <Chip label="Single Review" size="small" />
            <Chip label="Set Review" size="small" />
            <Chip label="Delta Review" size="small" />
            <Chip label="Standards" size="small" />
          </Box>
        </CardContent>
      </Card>
    </Stack>
  );
}
