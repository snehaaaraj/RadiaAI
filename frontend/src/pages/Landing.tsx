import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import BuildCircleIcon from '@mui/icons-material/BuildCircle';
import InsightsIcon from '@mui/icons-material/Insights';
import SecurityIcon from '@mui/icons-material/Security';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Container from '@mui/material/Container';
import Grid from '@mui/material/Grid2';
import Stack from '@mui/material/Stack';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import { alpha, useTheme } from '@mui/material/styles';
import { motion } from 'framer-motion';
import { TopBar } from '@/components/layout/TopBar';
import { useNavigate } from 'react-router-dom';
import { RadiaMark } from '@/components/layout/RadiaMark';
import { useAppContext } from '@/context/AppContext';
import { NavigationGuardProvider } from '@/context/NavigationGuardContext';
import { APP_NAME, HEADER_HEIGHT, ROUTES } from '@/utils/constants';

const highlights = [
  {
    title: 'Deterministic Reviews',
    description: 'Every result is structured, explainable, and repeatable across teams.',
    icon: <BuildCircleIcon color="primary" />,
  },
  {
    title: 'Traceability Ready',
    description: 'Track quality findings, deltas, and requirement history with clarity.',
    icon: <InsightsIcon color="secondary" />,
  },
  {
    title: 'Governance First',
    description: 'Built for engineering workflows where quality and compliance both matter.',
    icon: <SecurityIcon sx={{ color: 'warning.main' }} />,
  },
] as const;

export default function Landing() {
  const theme = useTheme();
  const navigate = useNavigate();
  const { defaultWorkspaceRoute, motionPreference } = useAppContext();
  const reduceMotion = motionPreference === 'reduced';
  const isDark = theme.palette.mode === 'dark';

  const pageGradient = isDark
    ? 'radial-gradient(circle at 14% 10%, rgba(66, 97, 127, 0.20) 0%, rgba(66, 97, 127, 0) 38%), linear-gradient(180deg, #10192B 0%, #0E1728 55%, #0D1624 100%)'
    : 'radial-gradient(circle at 12% 8%, rgba(123, 156, 188, 0.22) 0%, rgba(123, 156, 188, 0) 42%), linear-gradient(180deg, #F7FAFD 0%, #F2F6FA 54%, #EEF3F8 100%)';

  const heroGradient = isDark
    ? 'linear-gradient(126deg, rgba(26, 37, 60, 0.82) 0%, rgba(22, 34, 55, 0.78) 46%, rgba(18, 31, 50, 0.80) 100%)'
    : 'linear-gradient(126deg, rgba(255, 255, 255, 0.90) 0%, rgba(247, 251, 255, 0.92) 54%, rgba(240, 246, 252, 0.90) 100%)';

  return (
    <NavigationGuardProvider>
      <TopBar />
      <Box sx={{ minHeight: '100vh', background: pageGradient }}>
        <Container maxWidth="lg" sx={{ minHeight: '100vh', py: { xs: 6, md: 10 } }}>
          <Toolbar sx={{ minHeight: `${HEADER_HEIGHT}px !important` }} />
          <Stack spacing={5}>
            <motion.div
              initial={reduceMotion ? false : { opacity: 0, y: 24 }}
              animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
              transition={{ duration: 0.45, ease: 'easeOut' }}
            >
              <Card
                sx={{
                  p: { xs: 1, md: 2 },
                  border: '1px solid',
                  borderColor: alpha(theme.palette.divider, isDark ? 0.55 : 0.9),
                  background: heroGradient,
                  boxShadow: isDark ? 'none' : '0 12px 30px rgba(38, 64, 90, 0.08)',
                }}
              >
                <CardContent>
                  <Stack spacing={3}>
                    <Box display="flex" alignItems="center" gap={1}>
                      <RadiaMark size={26} />
                      <Typography variant="subtitle2" color="text.secondary">
                        Welcome to {APP_NAME}
                      </Typography>
                    </Box>
                    <Typography variant="h3" fontWeight={800} maxWidth={840}>
                      Intelligent requirements quality review, built for modern engineering teams.
                    </Typography>
                    <Typography variant="body1" color="text.secondary" maxWidth={780}>
                      Start from a polished workspace tailored to your preferences, then run requirement
                      set, single, and delta workflows with consistent output quality.
                    </Typography>
                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                      <Button variant="contained" size="large" onClick={() => navigate(defaultWorkspaceRoute)}>
                        Enter workspace
                      </Button>
                      <Button variant="outlined" size="large" onClick={() => navigate(ROUTES.SETTINGS)}>
                        Personalize experience
                      </Button>
                    </Stack>
                  </Stack>
                </CardContent>
              </Card>
            </motion.div>

            <Grid container spacing={2}>
              {highlights.map((highlight, index) => (
                <Grid key={highlight.title} size={{ xs: 12, md: 4 }}>
                  <motion.div
                    initial={reduceMotion ? false : { opacity: 0, y: 16 }}
                    animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
                    transition={{ duration: 0.35, ease: 'easeOut', delay: 0.08 * (index + 1) }}
                    whileHover={reduceMotion ? undefined : { y: -4 }}
                  >
                    <Card
                      sx={{
                        height: '100%',
                        border: '1px solid',
                        borderColor: alpha(theme.palette.divider, isDark ? 0.6 : 0.9),
                        backgroundColor: isDark
                          ? alpha('#1B2A42', 0.72)
                          : alpha('#FFFFFF', 0.84),
                      }}
                    >
                      <CardContent>
                        <Box mb={1.5}>{highlight.icon}</Box>
                        <Typography variant="h6" fontWeight={700} gutterBottom>
                          {highlight.title}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {highlight.description}
                        </Typography>
                      </CardContent>
                    </Card>
                  </motion.div>
                </Grid>
              ))}
            </Grid>

            <motion.div
              initial={reduceMotion ? false : { opacity: 0 }}
              animate={reduceMotion ? {} : { opacity: 1 }}
              transition={{ duration: 0.45, delay: 0.22 }}
            >
              <Box display="flex" alignItems="center" gap={1} color="text.secondary">
                <AutoAwesomeIcon fontSize="small" />
                <Typography variant="body2">
                  Tip: set your preferred default workspace page in Settings so “Enter workspace” takes
                  you exactly where you want to start.
                </Typography>
              </Box>
            </motion.div>
          </Stack>
        </Container>
      </Box>
    </NavigationGuardProvider>
  );
}
