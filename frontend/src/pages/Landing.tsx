import BuildCircleIcon from '@mui/icons-material/BuildCircle';
import InsightsIcon from '@mui/icons-material/Insights';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Container from '@mui/material/Container';
import Grid from '@mui/material/Grid2';
import Stack from '@mui/material/Stack';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import { alpha, useTheme } from '@mui/material/styles';
import { motion } from 'framer-motion';
import { TopBar } from '@/components/layout/TopBar';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { RadiaMark } from '@/components/layout/RadiaMark';
import { useAppContext } from '@/context/useAppContext';
import { NavigationGuardProvider } from '@/context/NavigationGuardContext';
import windrunnerLanding from '@/assets/windrunner-landing.png';
import { APP_NAME, HEADER_HEIGHT, ROUTES } from '@/utils/constants';
import { msalInstance, signIn } from '@/auth/msal';
import { useIsAuthenticated } from '@azure/msal-react';
import LoginIcon from '@mui/icons-material/Login';

const highlights = [
  {
    title: 'AI-Powered Reviews',
    description: 'Every result is structured, explainable, and repeatable across teams.',
    icon: <BuildCircleIcon color="primary" />,
  },
  {
    title: 'Traceability Ready',
    description: 'Track quality findings, deltas, and requirement history with clarity.',
    icon: <InsightsIcon color="secondary" />,
  },
] as const;

type ToolResource = {
  id: 'jama-requirement-review' | 'jama-roundtrip';
  label: string;
  description: string;
  route: string;
  ctaLabel: string;
};

const TOOL_RESOURCES: ToolResource[] = [
  {
    id: 'jama-requirement-review',
    label: 'Jama Requirement Review',
    description:
      'Run AI-powered quality checks for Jama requirements with explainable findings/suggestions and resource traceability-ready outputs.',
    route: ROUTES.HOME,
    ctaLabel: 'Open workspace',
  },
  {
    id: 'jama-roundtrip',
    label: 'Jama Roundtrip',
    description:
      'Use the dedicated placeholder page to reserve structure for future Jama roundtrip automation, orchestration, and reporting flows.',
    route: ROUTES.JAMA_ROUNDTRIP,
    ctaLabel: 'Open placeholder',
  },
];

const DEFAULT_TOOL_ID: ToolResource['id'] = 'jama-requirement-review';

export default function Landing() {
  const theme = useTheme();
  const navigate = useNavigate();
  const { motionPreference } = useAppContext();
  const reduceMotion = motionPreference === 'reduced';
  const isDark = theme.palette.mode === 'dark';
  const resourcesRef = useRef<HTMLDivElement | null>(null);
  const scrollToResources = () => resourcesRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  const [searchParams] = useSearchParams();
  const requestedToolId = searchParams.get('tool');
  const requestedTabToolId: ToolResource['id'] = requestedToolId === 'jama-roundtrip' ? 'jama-roundtrip' : DEFAULT_TOOL_ID;
  const [selectedToolId, setSelectedToolId] = useState<ToolResource['id']>(requestedTabToolId);

  useEffect(() => {
    setSelectedToolId(requestedTabToolId);
  }, [requestedTabToolId]);

  const selectedTool = TOOL_RESOURCES.find((tool) => tool.id === selectedToolId) ?? TOOL_RESOURCES[0];

  const pageGradient = isDark
    ? 'radial-gradient(circle at 14% 10%, rgba(66, 97, 127, 0.20) 0%, rgba(66, 97, 127, 0) 38%), linear-gradient(180deg, #10192B 0%, #0E1728 55%, #0D1624 100%)'
    : 'radial-gradient(circle at 12% 8%, rgba(123, 156, 188, 0.22) 0%, rgba(123, 156, 188, 0) 42%), linear-gradient(180deg, #F7FAFD 0%, #F2F6FA 54%, #EEF3F8 100%)';

  const heroGradient = isDark
    ? 'linear-gradient(126deg, rgba(26, 37, 60, 0.82) 0%, rgba(22, 34, 55, 0.78) 46%, rgba(18, 31, 50, 0.80) 100%)'
    : 'linear-gradient(126deg, rgba(255, 255, 255, 0.90) 0%, rgba(247, 251, 255, 0.92) 54%, rgba(240, 246, 252, 0.90) 100%)';

  return (
    <NavigationGuardProvider>
      <TopBar mode="landing" />
      <Box
        sx={{
          minHeight: '100vh',
          background: pageGradient,
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            overflow: 'hidden',
          }}
        >
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              backgroundImage: `url(${windrunnerLanding})`,
              backgroundPosition: 'center',
              backgroundRepeat: 'no-repeat',
              backgroundSize: 'cover',
              opacity: isDark ? 0.82 : 0.78,
            }}
          />
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              background: isDark
                ? 'linear-gradient(90deg, rgba(10,16,28,0.72) 0%, rgba(10,16,28,0.68) 36%, rgba(10,16,28,0.58) 100%)'
                : 'linear-gradient(90deg, rgba(247,250,254,0.84) 0%, rgba(247,250,254,0.70) 36%, rgba(247,250,254,0.56) 100%)',
            }}
          />
        </Box>
        <Container
          maxWidth="lg"
          sx={{
            position: 'relative',
            zIndex: 1,
            flexGrow: 1,
            py: { xs: 6, md: 10 },
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <Toolbar sx={{ minHeight: `${HEADER_HEIGHT}px !important` }} />
          <Stack spacing={5} sx={{ pb: { xs: 5, md: 7 } }}>
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
                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                      {msalInstance ? (
                        <LandingAuthAction onEnterWorkspace={scrollToResources} />
                      ) : (
                        <Button
                          variant="contained"
                          size="large"
                          onClick={scrollToResources}
                        >
                          Enter workspace
                        </Button>
                      )}
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
                <Grid key={highlight.title} size={{ xs: 12, md: 6 }}>
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

            <Box ref={resourcesRef}>
              <motion.div
                initial={reduceMotion ? false : { opacity: 0, y: 16 }}
                animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
                transition={{ duration: 0.35, ease: 'easeOut', delay: 0.16 }}
              >
                <Card
                  sx={{
                    border: '1px solid',
                    borderColor: alpha(theme.palette.divider, isDark ? 0.55 : 0.9),
                    backgroundColor: isDark ? alpha('#1A2640', 0.78) : alpha('#FFFFFF', 0.86),
                  }}
                >
                  <CardContent sx={{ p: { xs: 2.5, md: 3.5 } }}>
                    <Stack spacing={2.5}>
                      <Box>
                        <Typography variant="h4" fontWeight={800} gutterBottom>
                          Radia AI Resources
                        </Typography>
                        <Typography variant="body1" color="text.secondary">
                          Browse available tools and launch each workspace from one place.
                        </Typography>
                      </Box>

                      <Tabs
                        value={selectedToolId}
                        onChange={(_event, value: ToolResource['id']) => setSelectedToolId(value)}
                        variant="scrollable"
                        allowScrollButtonsMobile
                      >
                        {TOOL_RESOURCES.map((tool) => (
                          <Tab key={tool.id} value={tool.id} label={tool.label} />
                        ))}
                      </Tabs>

                      <Card variant="outlined">
                        <CardContent>
                          <Stack spacing={2}>
                            <Typography variant="h6" fontWeight={700}>
                              {selectedTool.label}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              {selectedTool.description}
                            </Typography>
                            <Box>
                              <Button variant="contained" onClick={() => navigate(selectedTool.route)}>
                                {selectedTool.ctaLabel}
                              </Button>
                            </Box>
                          </Stack>
                        </CardContent>
                      </Card>
                    </Stack>
                  </CardContent>
                </Card>
              </motion.div>
            </Box>
          </Stack>
        </Container>
      </Box>
    </NavigationGuardProvider>
  );
}

function LandingAuthAction({ onEnterWorkspace }: { onEnterWorkspace: () => void }) {
  const isAuthenticated = useIsAuthenticated();

  if (isAuthenticated) {
    return (
      <Button
        variant="contained"
        size="large"
        onClick={onEnterWorkspace}
      >
        Enter workspace
      </Button>
    );
  }

  return (
    <Button
      variant="contained"
      size="large"
      startIcon={<LoginIcon />}
      onClick={() => void signIn()}
    >
      Sign in with Microsoft
    </Button>
  );
}
