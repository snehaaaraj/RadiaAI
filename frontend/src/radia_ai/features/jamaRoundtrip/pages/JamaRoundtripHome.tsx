import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Container from '@mui/material/Container';
import Stack from '@mui/material/Stack';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import { alpha, useTheme } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';
import { TopBar } from '@/components/layout/TopBar';
import { NavigationGuardProvider } from '@/context/NavigationGuardContext';
import { HEADER_HEIGHT, ROUTES } from '@/utils/constants';

export default function JamaRoundtripHome() {
  const theme = useTheme();
  const navigate = useNavigate();
  const isDark = theme.palette.mode === 'dark';

  return (
    <NavigationGuardProvider>
      <TopBar mode="landing" />
      <Box
        sx={{
          minHeight: '100vh',
          background: isDark
            ? 'linear-gradient(180deg, #10192B 0%, #0E1728 55%, #0D1624 100%)'
            : 'linear-gradient(180deg, #F7FAFD 0%, #F2F6FA 54%, #EEF3F8 100%)',
        }}
      >
        <Container maxWidth="md" sx={{ py: { xs: 6, md: 9 } }}>
          <Toolbar sx={{ minHeight: `${HEADER_HEIGHT}px !important` }} />
          <Card
            sx={{
              border: '1px solid',
              borderColor: alpha(theme.palette.divider, isDark ? 0.55 : 0.9),
              backgroundColor: isDark ? alpha('#1A2640', 0.78) : alpha('#FFFFFF', 0.9),
            }}
          >
            <CardContent sx={{ p: { xs: 2.5, md: 3.5 } }}>
              <Stack spacing={2.5}>
                <Box>
                  <Typography variant="h4" fontWeight={800} gutterBottom>
                    Jama Roundtrip
                  </Typography>
                  <Typography variant="body1" color="text.secondary">
                    This page is the reserved feature placeholder for future Jama roundtrip import,
                    export, synchronization, and reporting workflows.
                  </Typography>
                </Box>

                <Card variant="outlined">
                  <CardContent>
                    <Stack spacing={1.5}>
                      <Typography variant="h6" fontWeight={700}>
                        Why this exists now
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        The frontend and backend are now being organized around project-named,
                        feature-first folders so new capabilities can land without mixing reviewer,
                        roundtrip, and shared platform code.
                      </Typography>
                    </Stack>
                  </CardContent>
                </Card>

                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                  <Button variant="contained" onClick={() => navigate(ROUTES.RADIA_AI_RESOURCES)}>
                    Back to resources
                  </Button>
                  <Button variant="outlined" onClick={() => navigate(ROUTES.HOME)}>
                    Open reviewer workspace
                  </Button>
                </Stack>
              </Stack>
            </CardContent>
          </Card>
        </Container>
      </Box>
    </NavigationGuardProvider>
  );
}
