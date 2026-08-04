import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid2';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import Button from '@mui/material/Button';
import LightModeIcon from '@mui/icons-material/LightMode';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import SettingsBrightnessIcon from '@mui/icons-material/SettingsBrightness';
import PaletteIcon from '@mui/icons-material/Palette';
import type { ReactNode } from 'react';
import { useAppContext, type ThemePreference } from '@/context/AppContext';

const THEMES: Array<{
  key: ThemePreference;
  title: string;
  description: string;
  icon: ReactNode;
}> = [
  {
    key: 'system',
    title: 'System',
    description: 'Follow your operating system preference automatically.',
    icon: <SettingsBrightnessIcon color="primary" />,
  },
  {
    key: 'light',
    title: 'Light',
    description: 'Bright workspace with crisp surfaces and high contrast.',
    icon: <LightModeIcon color="warning" />,
  },
  {
    key: 'dark',
    title: 'Dark',
    description: 'Reduce eye strain with a dark production workspace.',
    icon: <DarkModeIcon color="secondary" />,
  },
];

export default function Settings() {
  const { themePreference, setThemePreference, sidebarOpen, setSidebarOpen } = useAppContext();

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" fontWeight={800} gutterBottom>
          Settings
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Customize the workspace appearance and behavior.
        </Typography>
      </Box>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 7 }}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1.25} mb={1.5}>
                <PaletteIcon color="primary" />
                <Typography variant="h6" fontWeight={700}>
                  Theme preferences
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" mb={2}>
                Choose how the app should look across all pages. The setting is saved in your browser.
              </Typography>

              <Grid container spacing={2}>
                {THEMES.map((theme) => (
                  <Grid key={theme.key} size={{ xs: 12, md: 4 }}>
                    <Card
                      variant={themePreference === theme.key ? 'elevation' : 'outlined'}
                      sx={{
                        height: '100%',
                        borderColor: themePreference === theme.key ? 'primary.main' : 'divider',
                        boxShadow: themePreference === theme.key ? 3 : undefined,
                      }}
                    >
                      <CardActionArea onClick={() => setThemePreference(theme.key)} sx={{ height: '100%' }}>
                        <CardContent>
                          <Box display="flex" alignItems="center" gap={1} mb={1}>
                            {theme.icon}
                            <Typography variant="subtitle1" fontWeight={700}>
                              {theme.title}
                            </Typography>
                          </Box>
                          <Typography variant="body2" color="text.secondary">
                            {theme.description}
                          </Typography>
                        </CardContent>
                      </CardActionArea>
                    </Card>
                  </Grid>
                ))}
              </Grid>

              <Divider sx={{ my: 2.5 }} />

              <Alert severity="info" sx={{ mb: 2 }}>
                Current theme: <strong>{themePreference}</strong>
              </Alert>

              <Box display="flex" alignItems="center" justifyContent="space-between" gap={2} flexWrap="wrap">
                <Box>
                  <Typography variant="subtitle2" fontWeight={700}>
                    Sidebar
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Keep the navigation drawer open by default.
                  </Typography>
                </Box>
                <FormControlLabel
                  control={<Switch checked={sidebarOpen} onChange={(_, checked) => setSidebarOpen(checked)} />}
                  label={sidebarOpen ? 'Open' : 'Collapsed'}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 5 }}>
          <Stack spacing={2}>
            <Card>
              <CardContent>
                <Typography variant="h6" fontWeight={700} gutterBottom>
                  What this controls
                </Typography>
                <Stack spacing={1}>
                  <Chip label="Theme preference" variant="outlined" />
                  <Chip label="Sidebar visibility" variant="outlined" />
                  <Chip label="Persisted locally" variant="outlined" />
                </Stack>
              </CardContent>
            </Card>

            <Card>
              <CardContent>
                <Typography variant="h6" fontWeight={700} gutterBottom>
                  Tips
                </Typography>
                <Typography variant="body2" color="text.secondary" mb={1.5}>
                  Dark mode is usually easier during long review sessions, while light mode keeps the
                  interface crisp for print-style work.
                </Typography>
                <Button variant="outlined" onClick={() => setThemePreference('system')}>
                  Reset to system
                </Button>
              </CardContent>
            </Card>
          </Stack>
        </Grid>
      </Grid>
    </Stack>
  );
}
