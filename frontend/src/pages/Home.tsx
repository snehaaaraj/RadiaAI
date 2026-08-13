import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid2';
import RuleIcon from '@mui/icons-material/Rule';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { alpha, useTheme } from '@mui/material/styles';
import { useAppContext } from '@/context/AppContext';
import windrunnerLanding from '@/assets/windrunner-landing.png';
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
  const theme = useTheme();
  const { data: health, isLoading } = useHealth();
  const { motionPreference } = useAppContext();
  const reduceMotion = motionPreference === 'reduced';
  const isDark = theme.palette.mode === 'dark';

  const pageGradient = isDark
    ? 'radial-gradient(circle at 14% 10%, rgba(66, 97, 127, 0.20) 0%, rgba(66, 97, 127, 0) 38%), linear-gradient(180deg, #10192B 0%, #0E1728 55%, #0D1624 100%)'
    : 'radial-gradient(circle at 12% 8%, rgba(123, 156, 188, 0.22) 0%, rgba(123, 156, 188, 0) 42%), linear-gradient(180deg, #F7FAFD 0%, #F2F6FA 54%, #EEF3F8 100%)';

  return (
    <Box
      sx={{
        position: 'relative',
        overflow: 'hidden',
        borderRadius: 3,
        minHeight: { xs: 620, md: 700 },
        background: pageGradient,
        p: { xs: 2, md: 3 },
        border: '1px solid',
        borderColor: alpha(theme.palette.divider, isDark ? 0.45 : 0.8),
      }}
    >
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          backgroundImage: `url(${windrunnerLanding})`,
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
          backgroundSize: 'cover',
          opacity: isDark ? 0.8 : 0.76,
        }}
      />
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background: isDark
            ? 'linear-gradient(90deg, rgba(10,16,28,0.74) 0%, rgba(10,16,28,0.68) 36%, rgba(10,16,28,0.60) 100%)'
            : 'linear-gradient(90deg, rgba(247,250,254,0.84) 0%, rgba(247,250,254,0.70) 36%, rgba(247,250,254,0.56) 100%)',
        }}
      />
      <Stack spacing={3} sx={{ position: 'relative', zIndex: 1 }}>
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
          <Box display="flex" justifyContent="flex-end" alignItems="center" gap={2}>
            <Typography variant="subtitle2" color="text.secondary">
              System status
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
                <Card sx={{ height: '100%', backdropFilter: 'blur(4px)' }}>
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
      </Stack>
    </Box>
  );
}
