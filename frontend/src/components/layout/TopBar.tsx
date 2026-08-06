import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import { useLocation } from 'react-router-dom';
import { useAppContext } from '@/context/AppContext';
import { useHealth } from '@/hooks/useHealth';
import { ROUTE_TITLES, SIDEBAR_COLLAPSED_WIDTH, SIDEBAR_WIDTH } from '@/utils/constants';

interface TopBarProps {
  drawerWidth?: number;
}

export function TopBar({ drawerWidth = SIDEBAR_WIDTH }: TopBarProps) {
  const { sidebarOpen } = useAppContext();
  const { data: health } = useHealth();
  const location = useLocation();
  const currentDrawerWidth = sidebarOpen ? drawerWidth : SIDEBAR_COLLAPSED_WIDTH;

  const statusColor = health?.status === 'ok' ? 'success' : health?.status === 'degraded' ? 'warning' : 'error';
  const pageTitle = ROUTE_TITLES[location.pathname] ?? 'Workspace';

  return (
    <AppBar
      position="fixed"
      color="inherit"
      sx={{
        width: `calc(100% - ${currentDrawerWidth}px)`,
        ml: `${currentDrawerWidth}px`,
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
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Stack spacing={0.25}>
            <Typography variant="h6" fontWeight={800} color="text.primary" noWrap>
              {pageTitle}
            </Typography>
            <Typography variant="caption" color="text.secondary" noWrap>
              Focused deterministic review workspace
            </Typography>
          </Stack>
        </Box>

        {health && (
          <Chip label={`API ${health.status}`} color={statusColor} size="small" variant="outlined" />
        )}
      </Toolbar>
    </AppBar>
  );
}
