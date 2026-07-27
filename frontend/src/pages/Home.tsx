import Grid from '@mui/material/Grid2';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Box from '@mui/material/Box';
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
    description: 'Run deterministic production-grade review on an entire specification.',
    icon: <PlaylistAddCheckIcon fontSize="large" color="primary" />,
    path: ROUTES.REVIEW_REQUIREMENT_SET,
    label: 'Open Set Review',
  },
  {
    title: 'Individual Requirement Review',
    description: 'Check language, structure, and verifiability for one requirement.',
    icon: <RuleIcon fontSize="large" color="secondary" />,
    path: ROUTES.REVIEW_REQUIREMENT,
    label: 'Open Single Review',
  },
  {
    title: 'Delta Review',
    description: 'Review only changed requirements and trace-link changes between revisions.',
    icon: <CompareArrowsIcon fontSize="large" sx={{ color: 'warning.main' }} />,
    path: ROUTES.REVIEW_DELTA,
    label: 'Open Delta Review',
  },
] as const;

export default function Home() {
  const navigate = useNavigate();
  const { data: health, isLoading } = useHealth();

  return (
    <Box>
      {/* Header */}
      <Box mb={4}>
        <Typography variant="h4" gutterBottom fontWeight={700}>
          Requirements Engineering Assistant
        </Typography>
        <Typography variant="body1" color="text.secondary" maxWidth={600}>
          Deterministic AI-assisted requirements engineering workflows with traceability,
          explainability, and reproducible outcomes.
        </Typography>
      </Box>

      {/* System status */}
      <Box mb={4} display="flex" alignItems="center" gap={1}>
        <Typography variant="subtitle2" color="text.secondary">
          System Status:
        </Typography>
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

      {/* Quick action cards */}
      <Grid container spacing={3}>
        {QUICK_ACTIONS.map(({ title, description, icon, path, label }) => (
          <Grid key={path} size={{ xs: 12, md: 4 }}>
            <Card
              sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                cursor: 'pointer',
                transition: 'transform 0.15s, box-shadow 0.15s',
                '&:hover': {
                  transform: 'translateY(-2px)',
                  boxShadow: 4,
                },
              }}
              onClick={() => navigate(path)}
            >
              <CardContent sx={{ flexGrow: 1 }}>
                <Box mb={2}>{icon}</Box>
                <Typography variant="h6" gutterBottom fontWeight={600}>
                  {title}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {description}
                </Typography>
              </CardContent>
              <Box px={2} pb={2}>
                <Button variant="outlined" size="small" onClick={() => navigate(path)}>
                  {label}
                </Button>
              </Box>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Dependency health */}
      {health?.dependencies && health.dependencies.length > 0 && (
        <Box mt={4}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            Dependency Health
          </Typography>
          <Box display="flex" gap={1} flexWrap="wrap">
            {health.dependencies.map((dep) => (
              <Chip
                key={dep.name}
                label={`${dep.name}: ${dep.status}`}
                color={dep.status === 'ok' ? 'success' : dep.status === 'degraded' ? 'warning' : 'error'}
                size="small"
                variant="outlined"
              />
            ))}
          </Box>
        </Box>
      )}
    </Box>
  );
}
