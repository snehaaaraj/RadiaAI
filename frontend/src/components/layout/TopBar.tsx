import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import MenuIcon from '@mui/icons-material/Menu';
import BoltIcon from '@mui/icons-material/Bolt';
import LightModeIcon from '@mui/icons-material/LightMode';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import SettingsBrightnessIcon from '@mui/icons-material/SettingsBrightness';
import Box from '@mui/material/Box';
import Tooltip from '@mui/material/Tooltip';
import { useAppContext } from '@/context/AppContext';
import { useHealth } from '@/hooks/useHealth';
import { APP_NAME } from '@/utils/constants';

const DRAWER_WIDTH = 240;

interface TopBarProps {
  drawerWidth?: number;
}

export function TopBar({ drawerWidth = DRAWER_WIDTH }: TopBarProps) {
  const { sidebarOpen, setSidebarOpen, themePreference, setThemePreference } = useAppContext();
  const { data: health } = useHealth();

  const statusColor = health?.status === 'ok' ? 'success' : health?.status === 'degraded' ? 'warning' : 'error';
  const themeIcon =
    themePreference === 'dark' ? (
      <DarkModeIcon fontSize="small" />
    ) : themePreference === 'light' ? (
      <LightModeIcon fontSize="small" />
    ) : (
      <SettingsBrightnessIcon fontSize="small" />
    );

  const nextTheme = themePreference === 'system' ? 'light' : themePreference === 'light' ? 'dark' : 'system';

  return (
    <AppBar
      position="fixed"
      color="inherit"
      sx={{
        width: sidebarOpen ? `calc(100% - ${drawerWidth}px)` : '100%',
        ml: sidebarOpen ? `${drawerWidth}px` : 0,
        transition: (t) =>
          t.transitions.create(['width', 'margin'], {
            easing: t.transitions.easing.sharp,
            duration: t.transitions.duration.leavingScreen,
          }),
        borderBottom: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Toolbar>
        <IconButton
          edge="start"
          aria-label="toggle sidebar"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          sx={{ mr: 2 }}
        >
          <MenuIcon />
        </IconButton>

        <BoltIcon color="primary" sx={{ mr: 1 }} />
        <Typography variant="h6" fontWeight={700} color="primary" sx={{ flexGrow: 1 }}>
          {APP_NAME}
        </Typography>

        <Box display="flex" alignItems="center" gap={1}>
          <Tooltip title={`Theme: ${themePreference}. Click to switch to ${nextTheme}.`}>
            <IconButton
              size="small"
              onClick={() => setThemePreference(nextTheme)}
              aria-label="change theme preference"
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 999,
              }}
            >
              {themeIcon}
            </IconButton>
          </Tooltip>
          <Chip label={themePreference} size="small" variant="outlined" />
          {health && (
            <Chip
              label={`API ${health.status}`}
              color={statusColor}
              size="small"
              variant="outlined"
            />
          )}
        </Box>
      </Toolbar>
    </AppBar>
  );
}
