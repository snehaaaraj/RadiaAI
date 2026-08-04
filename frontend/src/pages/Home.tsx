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
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ShieldIcon from '@mui/icons-material/Shield';
import TraceIcon from '@mui/icons-material/AltRoute';
import { useNavigate } from 'react-router-dom';
import { useHealth } from '@/hooks/useHealth';
import { ROUTES } from '@/utils/constants';

const QUICK_ACTIONS = [
  {
    title: 'Requirement Set Review',
    description: 'Review an entire specification for duplicates, overlaps, contradictions, and traceability gaps.',
    icon: <PlaylistAddCheckIcon fontSize="large" color="primary" />,
    path: ROUTES.REVIEW_REQUIREMENT_SET,
    label: 'Open Set Review',
    accent: 'linear-gradient(135deg, rgba(27,79,216,0.14), rgba(27,79,216,0.04))',
  },
  {
    title: 'Single Requirement Review',
    description: 'Check one requirement for language, structure, and verifiability in a deterministic pass.',
    icon: <RuleIcon fontSize="large" color="secondary" />,
    path: ROUTES.REVIEW_REQUIREMENT,
    label: 'Open Single Review',
    accent: 'linear-gradient(135deg, rgba(107,33,168,0.14), rgba(107,33,168,0.04))',
  },
  {
    title: 'Delta Review',
    description: 'Review only the requirements and trace links that changed between revisions.',
    icon: <CompareArrowsIcon fontSize="large" sx={{ color: 'warning.main' }} />,
    path: ROUTES.REVIEW_DELTA,
    label: 'Open Delta Review',
    accent: 'linear-gradient(135deg, rgba(217,119,6,0.14), rgba(217,119,6,0.04))',
  },
] as const;

const FEATURES = [
  {
    icon: <AutoAwesomeIcon color="primary" />,
    title: 'Deterministic',
    text: 'Same input, same standards, same config = same result.',
  },
  {
    icon: <ShieldIcon color="secondary" />,
    title: 'Explainable',
    text: 'Every finding includes evidence, rule, and recommendation.',
  },
  {
    icon: <TraceIcon sx={{ color: 'warning.main' }} />,
    title: 'Traceable',
    text: 'Review history and dispositions stay attached to each run.',
  },
] as const;

export default function Home() {
  const navigate = useNavigate();
  const { data: health, isLoading } = useHealth();

  return (
    <Stack spacing={4}>
      <Card
        sx={{
          overflow: 'hidden',
          background:
            'linear-gradient(135deg, rgba(27,79,216,0.92), rgba(107,33,168,0.88))',
          color: 'common.white',
        }}
      >
        <CardContent sx={{ p: { xs: 3, md: 4 } }}>
          <Grid container spacing={3} alignItems="center">
            <Grid size={{ xs: 12, md: 8 }}>
              <Stack spacing={2}>
                <Box>
                  <Chip
                    label="Requirements Engineering Workspace"
                    size="small"
                    sx={{ bgcolor: 'rgba(255,255,255,0.16)', color: 'common.white' }}
                  />
                </Box>
                <Typography variant="h4" fontWeight={800} letterSpacing="-0.03em">
                  Deterministic AI-assisted requirements reviews for aerospace teams
                </Typography>
                <Typography variant="body1" sx={{ color: 'rgba(255,255,255,0.86)', maxWidth: 720 }}>
                  Review requirements, specifications, and deltas with reproducible outcomes,
                  engineering standards, and clear explainability — not a chatbot.
                </Typography>
                <Box display="flex" gap={1} flexWrap="wrap">
                  <Chip label="INCOSE" sx={{ bgcolor: 'rgba(255,255,255,0.16)', color: 'common.white' }} />
                  <Chip label="EARS" sx={{ bgcolor: 'rgba(255,255,255,0.16)', color: 'common.white' }} />
                  <Chip
                    label="Requirement Set Review"
                    sx={{ bgcolor: 'rgba(255,255,255,0.16)', color: 'common.white' }}
                  />
                </Box>
                <Box display="flex" gap={1.5} flexWrap="wrap">
                  <Button
                    variant="contained"
                    color="inherit"
                    onClick={() => navigate(ROUTES.REVIEW_REQUIREMENT_SET)}
                    sx={{ color: 'primary.dark', bgcolor: 'common.white', '&:hover': { bgcolor: '#E2E8F0' } }}
                  >
                    Start set review
                  </Button>
                  <Button
                    variant="outlined"
                    onClick={() => navigate(ROUTES.STANDARDS)}
                    sx={{ borderColor: 'rgba(255,255,255,0.6)', color: 'common.white' }}
                  >
                    View standards
                  </Button>
                </Box>
              </Stack>
            </Grid>

            <Grid size={{ xs: 12, md: 4 }}>
              <Card
                sx={{
                  bgcolor: 'rgba(255,255,255,0.14)',
                  color: 'common.white',
                  backdropFilter: 'blur(10px)',
                }}
              >
                <CardContent>
                  <Typography variant="overline" sx={{ color: 'rgba(255,255,255,0.75)' }}>
                    Live system health
                  </Typography>
                  <Box mt={1} mb={2}>
                    {isLoading ? (
                      <Chip label="Checking..." sx={{ bgcolor: 'rgba(255,255,255,0.16)', color: 'white' }} />
                    ) : (
                      <Chip
                        icon={<CheckCircleIcon />}
                        label={`API ${health?.status ?? 'unknown'} — v${health?.version ?? '—'}`}
                        sx={{ bgcolor: 'rgba(255,255,255,0.16)', color: 'white' }}
                      />
                    )}
                  </Box>
                  <Divider sx={{ borderColor: 'rgba(255,255,255,0.18)', my: 2 }} />
                  <Stack spacing={1.25}>
                    <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.84)' }}>
                      • Requirement Set Review is the default production workflow
                    </Typography>
                    <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.84)' }}>
                      • Standards can be pulled from SharePoint
                    </Typography>
                    <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.84)' }}>
                      • Review history captures dispositions and comments
                    </Typography>
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      <Grid container spacing={2}>
        {FEATURES.map((feature) => (
          <Grid key={feature.title} size={{ xs: 12, md: 4 }}>
            <Card>
              <CardContent>
                <Box display="flex" alignItems="center" gap={1.25} mb={1}>
                  {feature.icon}
                  <Typography variant="h6" fontWeight={700}>
                    {feature.title}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  {feature.text}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Box>
        <Typography variant="h5" gutterBottom fontWeight={700}>
          Quick actions
        </Typography>
        <Typography variant="body2" color="text.secondary" mb={2}>
          Jump straight into the review workflow that matches your task.
        </Typography>

        <Grid container spacing={3}>
          {QUICK_ACTIONS.map(({ title, description, icon, path, label, accent }) => (
            <Grid key={path} size={{ xs: 12, md: 4 }}>
              <Card
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  cursor: 'pointer',
                  background: accent,
                }}
                onClick={() => navigate(path)}
              >
                <CardContent sx={{ flexGrow: 1 }}>
                  <Box mb={2}>{icon}</Box>
                  <Typography variant="h6" gutterBottom fontWeight={700}>
                    {title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {description}
                  </Typography>
                </CardContent>
                <Box px={2} pb={2}>
                  <Button variant="contained" size="small" onClick={() => navigate(path)}>
                    {label}
                  </Button>
                </Box>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>

      {health?.dependencies && health.dependencies.length > 0 && (
        <Box>
          <Typography variant="h6" fontWeight={700} gutterBottom>
            Dependency health
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
    </Stack>
  );
}
