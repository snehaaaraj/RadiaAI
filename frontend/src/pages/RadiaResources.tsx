import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Container from '@mui/material/Container';
import Stack from '@mui/material/Stack';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import { alpha, useTheme } from '@mui/material/styles';
import { useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { TopBar } from '@/components/layout/TopBar';
import { NavigationGuardProvider } from '@/context/NavigationGuardContext';
import windrunnerLanding from '@/assets/windrunner-landing.png';
import { HEADER_HEIGHT, ROUTES } from '@/utils/constants';

type ToolResource = {
  id: 'jama-requirement-review' | 'jama-roundtrip';
  label: string;
  description: string;
  route: string | null;
};

const TOOL_RESOURCES: ToolResource[] = [
  {
    id: 'jama-requirement-review',
    label: 'Jama Requirement Review',
    description:
      'Run deterministic quality checks for Jama requirements with explainable findings/suggestions and resource traceability-ready outputs.',
    route: ROUTES.HOME,
  },
  {
    id: 'jama-roundtrip',
    label: 'Jama Roundtrip',
    description:
      'Simplify Jama Roundtrip tasks with automated scripts. This tool is planned and will be added here when ready.',
    route: null,
  },
];

const DEFAULT_TOOL_ID: ToolResource['id'] = 'jama-requirement-review';

export default function RadiaResources() {
  const theme = useTheme();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isDark = theme.palette.mode === 'dark';

  const requestedToolId = searchParams.get('tool');
  const initialToolId = useMemo<ToolResource['id']>(() => {
    if (requestedToolId === 'jama-roundtrip') return 'jama-roundtrip';
    return DEFAULT_TOOL_ID;
  }, [requestedToolId]);
  const [selectedToolId, setSelectedToolId] = useState<ToolResource['id']>(initialToolId);

  const selectedTool = TOOL_RESOURCES.find((tool) => tool.id === selectedToolId) ?? TOOL_RESOURCES[0];

  const pageGradient = isDark
    ? 'radial-gradient(circle at 14% 10%, rgba(66, 97, 127, 0.20) 0%, rgba(66, 97, 127, 0) 38%), linear-gradient(180deg, #10192B 0%, #0E1728 55%, #0D1624 100%)'
    : 'radial-gradient(circle at 12% 8%, rgba(123, 156, 188, 0.22) 0%, rgba(123, 156, 188, 0) 42%), linear-gradient(180deg, #F7FAFD 0%, #F2F6FA 54%, #EEF3F8 100%)';

  return (
    <NavigationGuardProvider>
      <TopBar showSearch={false} mode="landing" />
      <Box sx={{ minHeight: '100vh', background: pageGradient, position: 'relative' }}>
        <Box sx={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden' }}>
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              backgroundImage: `url(${windrunnerLanding})`,
              backgroundPosition: 'center',
              backgroundRepeat: 'no-repeat',
              backgroundSize: 'cover',
              opacity: isDark ? 0.78 : 0.74,
            }}
          />
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              background: isDark
                ? 'linear-gradient(90deg, rgba(10,16,28,0.74) 0%, rgba(10,16,28,0.68) 36%, rgba(10,16,28,0.60) 100%)'
                : 'linear-gradient(90deg, rgba(247,250,254,0.84) 0%, rgba(247,250,254,0.70) 36%, rgba(247,250,254,0.56) 100%)',
            }}
          />
        </Box>

        <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 1, py: { xs: 6, md: 9 } }}>
          <Toolbar sx={{ minHeight: `${HEADER_HEIGHT}px !important` }} />
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
                        <Button
                          variant="contained"
                          disabled={!selectedTool.route}
                          onClick={() => {
                            if (selectedTool.route) navigate(selectedTool.route);
                          }}
                        >
                          {selectedTool.route ? 'Open workspace' : 'Coming soon'}
                        </Button>
                      </Box>
                    </Stack>
                  </CardContent>
                </Card>
              </Stack>
            </CardContent>
          </Card>
        </Container>
      </Box>
    </NavigationGuardProvider>
  );
}
