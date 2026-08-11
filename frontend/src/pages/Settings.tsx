import DarkModeIcon from '@mui/icons-material/DarkMode';
import LightModeIcon from '@mui/icons-material/LightMode';
import PaletteIcon from '@mui/icons-material/Palette';
import SettingsBrightnessIcon from '@mui/icons-material/SettingsBrightness';
import TuneIcon from '@mui/icons-material/Tune';
import ViewCompactAltIcon from '@mui/icons-material/ViewCompactAlt';
import ViewComfyAltIcon from '@mui/icons-material/ViewComfyAlt';
import MotionPhotosAutoIcon from '@mui/icons-material/MotionPhotosAuto';
import ReduceCapacityIcon from '@mui/icons-material/ReduceCapacity';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import FormControlLabel from '@mui/material/FormControlLabel';
import Grid from '@mui/material/Grid2';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import {
  useAppContext,
  type AccentColor,
  type ThemePreference,
  type WorkspaceStartPage,
} from '@/context/AppContext';
import { ROUTES } from '@/utils/constants';

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

const ACCENTS: Array<{ key: AccentColor; label: string; color: string }> = [
  { key: 'indigo', label: 'Indigo', color: '#4F78E3' },
  { key: 'violet', label: 'Violet', color: '#A855F7' },
  { key: 'teal', label: 'Teal', color: '#14B8A6' },
  { key: 'rose', label: 'Rose', color: '#FB7185' },
];

const START_PAGE_OPTIONS: Array<{ value: WorkspaceStartPage; label: string }> = [
  { value: ROUTES.HOME, label: 'Workspace Home' },
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
    accentColor,
    setAccentColor,
    sidebarOpen,
    setSidebarOpen,
    uiDensity,
    setUiDensity,
    motionPreference,
    setMotionPreference,
    defaultWorkspaceRoute,
    setDefaultWorkspaceRoute,
    resetPersonalization,
  } = useAppContext();

  const reduceMotion = motionPreference === 'reduced';

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
            Personalize your workspace visuals, motion, layout density, and startup behavior.
          </Typography>
        </Box>
      </motion.div>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 8 }}>
          <Stack spacing={2}>
            <motion.div
              initial={reduceMotion ? false : { opacity: 0, y: 12 }}
              animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
              transition={{ duration: 0.28, ease: 'easeOut', delay: 0.05 }}
            >
              <Card>
                <CardContent>
                  <Box display="flex" alignItems="center" gap={1.25} mb={1.5}>
                    <PaletteIcon color="primary" />
                    <Typography variant="h6" fontWeight={700}>
                      Theme mode
                    </Typography>
                  </Box>
                  <Grid container spacing={1.5}>
                    {THEMES.map((theme) => (
                      <Grid key={theme.key} size={{ xs: 12, md: 4 }}>
                        <motion.div whileHover={reduceMotion ? undefined : { y: -3 }}>
                          <Card
                            variant={themePreference === theme.key ? 'elevation' : 'outlined'}
                            sx={{
                              height: '100%',
                              borderColor: themePreference === theme.key ? 'primary.main' : 'divider',
                              boxShadow: themePreference === theme.key ? 3 : undefined,
                            }}
                          >
                            <CardActionArea
                              onClick={() => setThemePreference(theme.key)}
                              sx={{ height: '100%' }}
                            >
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
                      </Grid>
                    ))}
                  </Grid>
                </CardContent>
              </Card>
            </motion.div>

            <motion.div
              initial={reduceMotion ? false : { opacity: 0, y: 12 }}
              animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
              transition={{ duration: 0.28, ease: 'easeOut', delay: 0.09 }}
            >
              <Card>
                <CardContent>
                  <Box display="flex" alignItems="center" gap={1.25} mb={1.5}>
                    <TuneIcon color="primary" />
                    <Typography variant="h6" fontWeight={700}>
                      Workspace style
                    </Typography>
                  </Box>
                  <Stack spacing={2.25}>
                    <Box>
                      <Typography variant="subtitle2" fontWeight={700} mb={1}>
                        Accent color
                      </Typography>
                      <Stack direction="row" flexWrap="wrap" gap={1}>
                        {ACCENTS.map((accent) => (
                          <motion.div key={accent.key} whileHover={reduceMotion ? undefined : { scale: 1.04 }}>
                            <Chip
                              onClick={() => setAccentColor(accent.key)}
                              clickable
                              label={accent.label}
                              color={accentColor === accent.key ? 'primary' : 'default'}
                              sx={{
                                borderWidth: 1,
                                borderStyle: 'solid',
                                borderColor: accent.color,
                                backgroundColor: accentColor === accent.key ? `${accent.color}22` : 'transparent',
                              }}
                            />
                          </motion.div>
                        ))}
                      </Stack>
                    </Box>

                    <Divider />

                    <Box display="flex" alignItems="center" justifyContent="space-between" gap={2} flexWrap="wrap">
                      <Box>
                        <Typography variant="subtitle2" fontWeight={700}>
                          Density
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Compact gives tighter lists and controls. Comfortable uses roomier spacing.
                        </Typography>
                      </Box>
                      <Button
                        variant={uiDensity === 'compact' ? 'contained' : 'outlined'}
                        startIcon={uiDensity === 'compact' ? <ViewCompactAltIcon /> : <ViewComfyAltIcon />}
                        onClick={() => setUiDensity(uiDensity === 'compact' ? 'comfortable' : 'compact')}
                      >
                        {uiDensity === 'compact' ? 'Compact' : 'Comfortable'}
                      </Button>
                    </Box>

                    <Box display="flex" alignItems="center" justifyContent="space-between" gap={2} flexWrap="wrap">
                      <Box>
                        <Typography variant="subtitle2" fontWeight={700}>
                          Motion
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Use expressive transitions across pages, or reduce for minimal movement.
                        </Typography>
                      </Box>
                      <Button
                        variant={motionPreference === 'reduced' ? 'outlined' : 'contained'}
                        startIcon={
                          motionPreference === 'reduced' ? <ReduceCapacityIcon /> : <MotionPhotosAutoIcon />
                        }
                        onClick={() => setMotionPreference(motionPreference === 'full' ? 'reduced' : 'full')}
                      >
                        {motionPreference === 'full' ? 'Full motion' : 'Reduced motion'}
                      </Button>
                    </Box>
                  </Stack>
                </CardContent>
              </Card>
            </motion.div>

            <motion.div
              initial={reduceMotion ? false : { opacity: 0, y: 12 }}
              animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
              transition={{ duration: 0.28, ease: 'easeOut', delay: 0.13 }}
            >
              <Card>
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
                        control={
                          <Switch checked={sidebarOpen} onChange={(_, checked) => setSidebarOpen(checked)} />
                        }
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
                          Used by the “Enter workspace” button on the landing page.
                        </Typography>
                      </Box>
                      <Select
                        size="small"
                        value={defaultWorkspaceRoute}
                        onChange={(event) =>
                          setDefaultWorkspaceRoute(event.target.value as WorkspaceStartPage)
                        }
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
          </Stack>
        </Grid>

        <Grid size={{ xs: 12, lg: 4 }}>
          <Stack spacing={2}>
            <motion.div
              initial={reduceMotion ? false : { opacity: 0, x: 14 }}
              animate={reduceMotion ? {} : { opacity: 1, x: 0 }}
              transition={{ duration: 0.3, ease: 'easeOut', delay: 0.14 }}
            >
              <Card>
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
        </Grid>
      </Grid>
    </Stack>
  );
}
