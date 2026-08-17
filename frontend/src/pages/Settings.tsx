import DarkModeIcon from '@mui/icons-material/DarkMode';
import LightModeIcon from '@mui/icons-material/LightMode';
import PaletteIcon from '@mui/icons-material/Palette';
import SettingsBrightnessIcon from '@mui/icons-material/SettingsBrightness';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import CardContent from '@mui/material/CardContent';
import Divider from '@mui/material/Divider';
import FormControlLabel from '@mui/material/FormControlLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';
import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { useAppContext, type ThemePreference, type WorkspaceStartPage } from '@/context/AppContext';
import { HEADER_HEIGHT, ROUTES } from '@/utils/constants';
import { SETTINGS_SECTION_IDS } from '@/utils/settingsSections';

const THEMES: Array<{
  key: ThemePreference;
  title: string;
  description: string;
  icon: ReactNode;
}> = [
  {
    key: 'system',
    title: 'System',
    description: 'Automatically follow operating system preference.',
    icon: <SettingsBrightnessIcon color="primary" />,
  },
  {
    key: 'light',
    title: 'Light',
    description: 'Crisp interface for daytime review and analysis.',
    icon: <LightModeIcon color="warning" />,
  },
  {
    key: 'dark',
    title: 'Dark',
    description: 'Lower eye strain for long quality sessions.',
    icon: <DarkModeIcon color="secondary" />,
  },
];

const START_PAGE_OPTIONS: Array<{ value: WorkspaceStartPage; label: string }> = [
  { value: ROUTES.HOME, label: 'Home' },
  { value: ROUTES.REVIEW_REQUIREMENT, label: 'Single Requirement Review' },
  { value: ROUTES.REVIEW_DELTA, label: 'Delta Review' },
  { value: ROUTES.REVIEW_HISTORY, label: 'Review History' },
  { value: ROUTES.STANDARDS, label: 'Standards' },
  { value: ROUTES.SEARCH, label: 'Search' },
  { value: ROUTES.CHAT, label: 'Chat' },
  { value: ROUTES.DOCUMENTS, label: 'Documents' },
];

export default function Settings() {
  const {
    themePreference,
    setThemePreference,
    sidebarOpen,
    setSidebarOpen,
    motionPreference,
    defaultWorkspaceRoute,
    setDefaultWorkspaceRoute,
    soundOnReviewComplete,
    setSoundOnReviewComplete,
    resetPersonalization,
  } = useAppContext();

  const reduceMotion = motionPreference === 'reduced';

  // On mount, scroll to the section indicated by the URL hash.
  // Wait for the page entrance animation to finish before scrolling
  // so getBoundingClientRect() returns the final painted position.
  useEffect(() => {
    const id = window.location.hash.replace('#', '');
    if (!id) return;
    // Entrance animation is 280ms (delay 0.18s + duration 0.28s max).
    // A 350ms wait covers both motion-full and motion-reduced paths.
    const timer = setTimeout(() => {
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({ behavior: reduceMotion ? 'instant' : 'smooth', block: 'start' });
    }, reduceMotion ? 0 : 350);
    return () => clearTimeout(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // intentionally run once on mount only

  return (
    <Stack spacing={3}>
      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 12 }}
        animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
        transition={{ duration: 0.28, ease: 'easeOut' }}
      >
        <Box>
          <Typography variant="h4" fontWeight={800} gutterBottom>
            Settings
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Universal Radia AI settings for theme, startup behavior, and notifications.
          </Typography>
        </Box>
      </motion.div>

      <Stack spacing={2}>
        <motion.div
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: 'easeOut', delay: 0.05 }}
        >
          <Card id={SETTINGS_SECTION_IDS.THEME_MODE} sx={{ scrollMarginTop: `${HEADER_HEIGHT + 24}px` }}>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1.25} mb={1.5}>
                <PaletteIcon color="primary" />
                <Typography variant="h6" fontWeight={700}>
                  Theme mode
                </Typography>
              </Box>
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
                {THEMES.map((theme) => (
                  <motion.div key={theme.key} whileHover={reduceMotion ? undefined : { y: -3 }} style={{ flex: 1 }}>
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
                  </motion.div>
                ))}
              </Stack>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: 'easeOut', delay: 0.1 }}
        >
          <Card id={SETTINGS_SECTION_IDS.STARTUP_BEHAVIOR} sx={{ scrollMarginTop: `${HEADER_HEIGHT + 24}px` }}>
            <CardContent>
              <Typography variant="h6" fontWeight={700} gutterBottom>
                Startup behavior
              </Typography>
              <Stack spacing={2}>
                <Box display="flex" alignItems="center" justifyContent="space-between" gap={2} flexWrap="wrap">
                  <Box>
                    <Typography variant="subtitle2" fontWeight={700}>
                      Sidebar
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Keep the navigation drawer open by default inside the workspace.
                    </Typography>
                  </Box>
                  <FormControlLabel
                    control={<Switch checked={sidebarOpen} onChange={(_, checked) => setSidebarOpen(checked)} />}
                    label={sidebarOpen ? 'Open' : 'Collapsed'}
                  />
                </Box>

                <Divider />

                <Box display="flex" alignItems="center" justifyContent="space-between" gap={2} flexWrap="wrap">
                  <Box>
                    <Typography variant="subtitle2" fontWeight={700}>
                      Default workspace page
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Used by the “Open workspace” button from resources.
                    </Typography>
                  </Box>
                  <Select
                    size="small"
                    value={defaultWorkspaceRoute}
                    onChange={(event) => setDefaultWorkspaceRoute(event.target.value as WorkspaceStartPage)}
                    sx={{ minWidth: 260 }}
                  >
                    {START_PAGE_OPTIONS.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: 'easeOut', delay: 0.14 }}
        >
          <Card id={SETTINGS_SECTION_IDS.REVIEW_NOTIFICATIONS} sx={{ scrollMarginTop: `${HEADER_HEIGHT + 24}px` }}>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1.25} mb={1.5}>
                <NotificationsActiveIcon color="primary" />
                <Typography variant="h6" fontWeight={700}>
                  Review notifications
                </Typography>
              </Box>
              <Box display="flex" alignItems="center" justifyContent="space-between" gap={2} flexWrap="wrap">
                <Box>
                  <Typography variant="subtitle2" fontWeight={700}>
                    Sound on review complete
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Play a short chime when a deterministic review finishes.
                  </Typography>
                </Box>
                <FormControlLabel
                  control={
                    <Switch
                      checked={soundOnReviewComplete}
                      onChange={(_, checked) => setSoundOnReviewComplete(checked)}
                    />
                  }
                  label={soundOnReviewComplete ? 'On' : 'Off'}
                />
              </Box>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: 'easeOut', delay: 0.18 }}
        >
          <Card id={SETTINGS_SECTION_IDS.RESET_PERSONALIZATION} sx={{ scrollMarginTop: `${HEADER_HEIGHT + 24}px` }}>
            <CardContent>
              <Typography variant="h6" fontWeight={700} gutterBottom>
                Reset personalization
              </Typography>
              <Typography variant="body2" color="text.secondary" mb={2}>
                Return all workspace personalization settings to recommended defaults.
              </Typography>
              <Button variant="outlined" color="inherit" onClick={resetPersonalization}>
                Reset all preferences
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </Stack>
    </Stack>
  );
}
