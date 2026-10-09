import DarkModeIcon from '@mui/icons-material/DarkMode';
import LightModeIcon from '@mui/icons-material/LightMode';
import PaletteIcon from '@mui/icons-material/Palette';
import SettingsBrightnessIcon from '@mui/icons-material/SettingsBrightness';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import LinkIcon from '@mui/icons-material/Link';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import Alert from '@mui/material/Alert';
import CircularProgress from '@mui/material/CircularProgress';
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
import { type ThemePreference, type WorkspaceStartPage } from '@/context/AppContext';
import { useAppContext } from '@/context/useAppContext';
import { HEADER_HEIGHT, ROUTES } from '@/utils/constants';
import { SETTINGS_SECTION_IDS } from '@/utils/settingsSections';
import { JamaAccountCard } from '@/radia_ai/features/jamaRequirementReviewer/components/JamaAccountCard';
import { getSettingsSectionCardSx, settingsStyles } from './Settings.styles';
import { useCurrentUser } from '@/hooks/useCurrentUser';
import { useIngestDocuments } from '@/hooks/useIngestDocuments';
import { useIngestionJobStatus } from '@/hooks/useIngestionJobStatus';

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
  const { data: currentUser } = useCurrentUser();
  const canManageDocuments = currentUser?.can_manage_documents ?? false;
  const {
    mutate: ingestDocuments,
    isPending: isIngesting,
    isSuccess,
    isError,
    data: ingestResult,
  } = useIngestDocuments();
  const { data: ingestionJob } = useIngestionJobStatus(ingestResult?.job_id ?? null);
  const ingestionFailureMessage = ingestionJob?.failure_details
    .map((failure) => [failure.filename, failure.error].filter(Boolean).join(': '))
    .join('; ');

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
            Universal Radia AI settings for your Jama account, theme, startup behavior, and
            notifications.
          </Typography>
        </Box>
      </motion.div>

      <Stack spacing={2}>
        <motion.div
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: 'easeOut', delay: 0.01 }}
        >
          <Card id={SETTINGS_SECTION_IDS.DOCUMENT_INGESTION} sx={getSettingsSectionCardSx(HEADER_HEIGHT)}>
            <CardContent>
              <Box sx={settingsStyles.sectionHeader}>
                <CloudUploadIcon color="primary" />
                <Typography variant="h6" fontWeight={700}>
                  Document ingestion
                </Typography>
              </Box>
              <Stack spacing={2} alignItems="flex-start">
                <Typography variant="body2" color="text.secondary">
                  Sync documents from SharePoint into the reviewer knowledge base. Only users with
                  document management access can start an ingestion.
                </Typography>
                {canManageDocuments && (
                  <Button
                    variant="contained"
                    startIcon={
                      isIngesting ? <CircularProgress size={16} color="inherit" /> : <CloudUploadIcon />
                    }
                    onClick={() => ingestDocuments({ source: 'sharepoint' })}
                    disabled={isIngesting}
                  >
                    {isIngesting ? 'Ingesting...' : 'Ingest Documents'}
                  </Button>
                )}
                {isSuccess && (
                  <Alert
                    severity={
                      ingestionJob?.status === 'failed'
                        ? 'error'
                        : ingestionJob?.status === 'completed'
                          ? 'success'
                          : 'info'
                    }
                    sx={{ width: '100%' }}
                  >
                    {ingestionJob?.status === 'failed'
                      ? `${ingestionJob.message} ${ingestionFailureMessage ?? ''}`
                      : ingestionJob?.message ?? ingestResult?.message ?? 'Ingestion job queued.'}
                  </Alert>
                )}
                {isError && (
                  <Alert severity="error" sx={{ width: '100%' }}>
                    Failed to trigger ingestion. Please check backend logs.
                  </Alert>
                )}
              </Stack>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: 'easeOut', delay: 0.02 }}
        >
          <Card id={SETTINGS_SECTION_IDS.JAMA_ACCOUNT} sx={getSettingsSectionCardSx(HEADER_HEIGHT)}>
            <CardContent>
              <Box sx={settingsStyles.sectionHeader}>
                <LinkIcon color="primary" />
                <Typography variant="h6" fontWeight={700}>
                  Jama account
                </Typography>
              </Box>
              <JamaAccountCard />
            </CardContent>
          </Card>
        </motion.div>

        <motion.div
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          animate={reduceMotion ? {} : { opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: 'easeOut', delay: 0.05 }}
        >
          <Card id={SETTINGS_SECTION_IDS.THEME_MODE} sx={getSettingsSectionCardSx(HEADER_HEIGHT)}>
            <CardContent>
              <Box sx={settingsStyles.sectionHeader}>
                <PaletteIcon color="primary" />
                <Typography variant="h6" fontWeight={700}>
                  Theme mode
                </Typography>
              </Box>
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
                {THEMES.map((theme) => (
                  <motion.div
                    key={theme.key}
                    whileHover={reduceMotion ? undefined : { y: -3 }}
                    style={settingsStyles.themeOptionWrapper}
                  >
                    <Card
                      variant={themePreference === theme.key ? 'elevation' : 'outlined'}
                      sx={settingsStyles.themeOptionCard(themePreference === theme.key)}
                    >
                      <CardActionArea onClick={() => setThemePreference(theme.key)} sx={settingsStyles.fullHeight}>
                        <CardContent>
                          <Box sx={settingsStyles.themeOptionHeader}>
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
          <Card id={SETTINGS_SECTION_IDS.STARTUP_BEHAVIOR} sx={getSettingsSectionCardSx(HEADER_HEIGHT)}>
            <CardContent>
              <Typography variant="h6" fontWeight={700} gutterBottom>
                Startup behavior
              </Typography>
              <Stack spacing={2}>
                <Box sx={settingsStyles.settingRow}>
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

                <Box sx={settingsStyles.settingRow}>
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
                    sx={settingsStyles.workspacePageSelect}
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
          <Card id={SETTINGS_SECTION_IDS.REVIEW_NOTIFICATIONS} sx={getSettingsSectionCardSx(HEADER_HEIGHT)}>
            <CardContent>
              <Box sx={settingsStyles.sectionHeader}>
                <NotificationsActiveIcon color="primary" />
                <Typography variant="h6" fontWeight={700}>
                  Review notifications
                </Typography>
              </Box>
              <Box sx={settingsStyles.settingRow}>
                <Box>
                  <Typography variant="subtitle2" fontWeight={700}>
                    Sound on review complete
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Play a short chime when a review finishes.
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
          <Card id={SETTINGS_SECTION_IDS.RESET_PERSONALIZATION} sx={getSettingsSectionCardSx(HEADER_HEIGHT)}>
            <CardContent>
              <Typography variant="h6" fontWeight={700} gutterBottom>
                Reset personalization
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={settingsStyles.resetDescription}>
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
