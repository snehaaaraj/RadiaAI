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
import ChatIcon from '@mui/icons-material/Chat';
import SearchIcon from '@mui/icons-material/Search';
import FolderIcon from '@mui/icons-material/Folder';
import SettingsIcon from '@mui/icons-material/Settings';
import BoltIcon from '@mui/icons-material/Bolt';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAppContext } from '@/context/AppContext';
import { ROUTES, APP_NAME } from '@/utils/constants';

const DRAWER_WIDTH = 240;

const NAV_ITEMS = [
  { label: 'Home', icon: <HomeIcon />, path: ROUTES.HOME },
  { label: 'Chat', icon: <ChatIcon />, path: ROUTES.CHAT },
  { label: 'Search', icon: <SearchIcon />, path: ROUTES.SEARCH },
  { label: 'Documents', icon: <FolderIcon />, path: ROUTES.DOCUMENTS },
] as const;

const BOTTOM_ITEMS = [
  { label: 'Settings', icon: <SettingsIcon />, path: ROUTES.SETTINGS },
] as const;

export function Sidebar() {
  const { sidebarOpen } = useAppContext();
  const navigate = useNavigate();
  const location = useLocation();

  const drawerContent = (
    <Box display="flex" flexDirection="column" height="100%">
      {/* Logo */}
      <Box display="flex" alignItems="center" gap={1} px={2} py={2}>
        <BoltIcon color="primary" />
        <Typography variant="h6" fontWeight={700} color="primary">
          {APP_NAME}
        </Typography>
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
                borderRadius: 1,
                '&.Mui-selected': {
                  bgcolor: 'primary.main',
                  color: 'white',
                  '& .MuiListItemIcon-root': { color: 'white' },
                  '&:hover': { bgcolor: 'primary.dark' },
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
