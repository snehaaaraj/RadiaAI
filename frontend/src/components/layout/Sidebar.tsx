import Drawer from '@mui/material/Drawer';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Divider from '@mui/material/Divider';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import HomeIcon from '@mui/icons-material/Home';
import RuleIcon from '@mui/icons-material/Rule';
import PlaylistAddCheckIcon from '@mui/icons-material/PlaylistAddCheck';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import HistoryIcon from '@mui/icons-material/History';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import SettingsIcon from '@mui/icons-material/Settings';
import BoltIcon from '@mui/icons-material/Bolt';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAppContext } from '@/context/AppContext';
import { ROUTES, APP_NAME } from '@/utils/constants';

const DRAWER_WIDTH = 240;

const NAV_ITEMS = [
  { label: 'Home', icon: <HomeIcon />, path: ROUTES.HOME },
  { label: 'Set Review', icon: <PlaylistAddCheckIcon />, path: ROUTES.REVIEW_REQUIREMENT_SET },
  { label: 'Single Review', icon: <RuleIcon />, path: ROUTES.REVIEW_REQUIREMENT },
  { label: 'Delta Review', icon: <CompareArrowsIcon />, path: ROUTES.REVIEW_DELTA },
  { label: 'Review History', icon: <HistoryIcon />, path: ROUTES.REVIEW_HISTORY },
  { label: 'Standards', icon: <MenuBookIcon />, path: ROUTES.STANDARDS },
] as const;

const BOTTOM_ITEMS = [
  { label: 'Launchpad', icon: <RocketLaunchIcon />, path: ROUTES.LANDING },
  { label: 'Settings', icon: <SettingsIcon />, path: ROUTES.SETTINGS },
] as const;

export function Sidebar() {
  const { sidebarOpen } = useAppContext();
  const navigate = useNavigate();
  const location = useLocation();

  const drawerContent = (
    <Box display="flex" flexDirection="column" height="100%">
      {/* Logo */}
      <Box
        mx={1.5}
        mt={1.5}
        mb={1}
        p={1.5}
        sx={{
          borderRadius: 3,
          background: 'linear-gradient(135deg, rgba(27,79,216,0.10), rgba(107,33,168,0.08))',
        }}
      >
        <Box display="flex" alignItems="center" gap={1}>
          <BoltIcon color="primary" />
          <Box>
            <Typography variant="h6" fontWeight={800} color="primary" lineHeight={1.1}>
              {APP_NAME}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Deterministic reviews
            </Typography>
          </Box>
        </Box>
      </Box>
      <Divider />

      {/* Primary navigation */}
      <List sx={{ flexGrow: 1, pt: 1 }}>
        {NAV_ITEMS.map(({ label, icon, path }) => (
          <ListItem key={path} disablePadding>
            <ListItemButton
              selected={location.pathname === path}
              onClick={() => navigate(path)}
              sx={{
                mx: 1,
                my: 0.5,
                borderRadius: 1,
                position: 'relative',
                overflow: 'hidden',
                transition: 'background-color 120ms ease, transform 120ms ease',
                '&::before': {
                  content: '""',
                  position: 'absolute',
                  left: 0,
                  top: 0,
                  bottom: 0,
                  width: 4,
                  bgcolor: 'transparent',
                },
                '&.Mui-selected': {
                  bgcolor: 'primary.main',
                  color: 'white',
                  '& .MuiListItemIcon-root': { color: 'white' },
                  '&:hover': { bgcolor: 'primary.dark' },
                  '&::before': {
                    bgcolor: 'secondary.main',
                  },
                },
                '&:hover': {
                  transform: 'translateX(2px)',
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 36 }}>{icon}</ListItemIcon>
              <ListItemText primary={label} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>

      <Divider />

      {/* Bottom navigation */}
      <List>
        {BOTTOM_ITEMS.map(({ label, icon, path }) => (
          <ListItem key={path} disablePadding>
            <ListItemButton
              selected={location.pathname === path}
              onClick={() => navigate(path)}
              sx={{ mx: 1, borderRadius: 1 }}
            >
              <ListItemIcon sx={{ minWidth: 36 }}>{icon}</ListItemIcon>
              <ListItemText primary={label} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>

      <Box px={2} pb={2}>
        <Typography variant="caption" color="text.secondary">
          v0.1.0 — Phase 1
        </Typography>
      </Box>
    </Box>
  );

  return (
    <Drawer
      variant="persistent"
      open={sidebarOpen}
      sx={{
        width: DRAWER_WIDTH,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: DRAWER_WIDTH,
          boxSizing: 'border-box',
          borderRight: '1px solid',
          borderColor: 'divider',
        },
      }}
    >
      {drawerContent}
    </Drawer>
  );
}
