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
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAppContext } from '@/context/AppContext';
import { useHealth } from '@/hooks/useHealth';
import { ROUTES } from '@/utils/constants';

const QUICK_ACTIONS = [
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
  const { motionPreference } = useAppContext();
  const reduceMotion = motionPreference === 'reduced';

  return (
    <Stack spacing={3}>
      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 10 }}
        animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
        transition={{ duration: 0.24, ease: 'easeOut' }}
      >
        <Box>
          <Typography variant="h4" gutterBottom fontWeight={700}>
            Workspace Home
          </Typography>
          <Typography variant="body1" color="text.secondary" maxWidth={720}>
            Deterministic review workflows for requirement quality, traceability, and revision control.
          </Typography>
        </Box>
      </motion.div>

      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 10 }}
        animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
        transition={{ duration: 0.24, ease: 'easeOut', delay: 0.06 }}
      >
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
      </motion.div>

      <Grid container spacing={2}>
        {QUICK_ACTIONS.map(({ title, description, icon, path, label }, index) => (
          <Grid key={path} size={{ xs: 12, md: 4 }}>
            <motion.div
              initial={reduceMotion ? false : { opacity: 0, y: 12 }}
              animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
              transition={{ duration: 0.22, ease: 'easeOut', delay: 0.07 * (index + 1) }}
              whileHover={reduceMotion ? undefined : { y: -4 }}
            >
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
            </motion.div>
          </Grid>
        ))}
      </Grid>

      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 10 }}
        animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
        transition={{ duration: 0.24, ease: 'easeOut', delay: 0.2 }}
      >
        <Card>
          <CardContent>
            <Typography variant="h6" fontWeight={700} gutterBottom>
              What this app does
            </Typography>
            <Typography variant="body2" color="text.secondary">
              It supports single requirement review, delta review, review history, and standards
              references for aerospace requirements engineering.
            </Typography>
            <Divider sx={{ my: 2 }} />
            <Box display="flex" gap={1} flexWrap="wrap" alignItems="center">
              <Chip label="Single Review" size="small" />
              <Chip label="Delta Review" size="small" />
              <Chip label="Standards" size="small" />
              <Chip icon={<RocketLaunchIcon />} label="Launch-ready workflow" size="small" />
            </Box>
          </CardContent>
        </Card>
      </motion.div>
    </Stack>
  );
}
