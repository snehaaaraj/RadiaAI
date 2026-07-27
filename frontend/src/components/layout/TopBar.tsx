import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import MenuIcon from '@mui/icons-material/Menu';
import BoltIcon from '@mui/icons-material/Bolt';
import Box from '@mui/material/Box';
import { useAppContext } from '@/context/AppContext';
import { useHealth } from '@/hooks/useHealth';
import { APP_NAME } from '@/utils/constants';

const DRAWER_WIDTH = 240;

interface TopBarProps {
  drawerWidth?: number;
}

export function TopBar({ drawerWidth = DRAWER_WIDTH }: TopBarProps) {
  const { sidebarOpen, setSidebarOpen } = useAppContext();
  const { data: health } = useHealth();

  const statusColor = health?.status === 'ok' ? 'success' : health?.status === 'degraded' ? 'warning' : 'error';

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
