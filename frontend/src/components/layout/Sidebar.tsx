import Drawer from '@mui/material/Drawer';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Divider from '@mui/material/Divider';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import HomeIcon from '@mui/icons-material/Home';
import RuleIcon from '@mui/icons-material/Rule';
import PlaylistAddCheckIcon from '@mui/icons-material/PlaylistAddCheck';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import HistoryIcon from '@mui/icons-material/History';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import SettingsIcon from '@mui/icons-material/Settings';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import MenuOpenIcon from '@mui/icons-material/MenuOpen';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAppContext } from '@/context/AppContext';
import { ROUTES, APP_NAME, SIDEBAR_COLLAPSED_WIDTH, SIDEBAR_WIDTH } from '@/utils/constants';
import { RadiaMark } from './RadiaMark';

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
  const { sidebarOpen, setSidebarOpen } = useAppContext();
  const navigate = useNavigate();
  const location = useLocation();
  const currentWidth = sidebarOpen ? SIDEBAR_WIDTH : SIDEBAR_COLLAPSED_WIDTH;

  const drawerContent = (
    <Box display="flex" flexDirection="column" height="100%">
      <Box
        mx={1.25}
        mt={1.25}
        mb={1}
        p={1.25}
        sx={{
          borderRadius: 3,
          background: 'linear-gradient(135deg, rgba(225,29,72,0.13), rgba(27,79,216,0.12))',
        }}
      >
        <Box display="flex" alignItems="center" justifyContent={sidebarOpen ? 'space-between' : 'center'} gap={1}>
          <Box display="flex" alignItems="center" gap={1.25} minWidth={0}>
            <RadiaMark size={34} />
            {sidebarOpen && (
              <Box minWidth={0}>
                <Typography variant="h6" fontWeight={800} color="text.primary" lineHeight={1.1} noWrap>
                  {APP_NAME}
                </Typography>
                <Typography variant="caption" color="text.secondary" noWrap>
                  Deterministic reviews
                </Typography>
              </Box>
            )}
          </Box>
          <Tooltip title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'} placement="right">
            <IconButton
              size="small"
              aria-label="toggle sidebar"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              sx={{
                color: 'text.secondary',
                transform: sidebarOpen ? 'none' : 'rotate(180deg)',
              }}
            >
              <MenuOpenIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
      <Divider />

      <List sx={{ flexGrow: 1, pt: 1 }}>
        {NAV_ITEMS.map(({ label, icon, path }) => (
          <ListItem key={path} disablePadding>
            <Tooltip title={sidebarOpen ? '' : label} placement="right">
              <ListItemButton
                selected={location.pathname === path}
                onClick={() => navigate(path)}
                sx={{
                  mx: 1,
                  my: 0.5,
                  px: sidebarOpen ? 1.5 : 1.25,
                  justifyContent: sidebarOpen ? 'flex-start' : 'center',
                  borderRadius: 1.5,
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
                    transform: sidebarOpen ? 'translateX(2px)' : 'none',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: sidebarOpen ? 36 : 0, mr: sidebarOpen ? 1 : 0 }}>
                  {icon}
                </ListItemIcon>
                {sidebarOpen && <ListItemText primary={label} />}
              </ListItemButton>
            </Tooltip>
          </ListItem>
        ))}
      </List>

      <Divider />

      <List>
        {BOTTOM_ITEMS.map(({ label, icon, path }) => (
          <ListItem key={path} disablePadding>
            <Tooltip title={sidebarOpen ? '' : label} placement="right">
              <ListItemButton
                selected={location.pathname === path}
                onClick={() => navigate(path)}
                sx={{
                  mx: 1,
                  px: sidebarOpen ? 1.5 : 1.25,
                  justifyContent: sidebarOpen ? 'flex-start' : 'center',
                  borderRadius: 1.5,
                }}
              >
                <ListItemIcon sx={{ minWidth: sidebarOpen ? 36 : 0, mr: sidebarOpen ? 1 : 0 }}>
                  {icon}
                </ListItemIcon>
                {sidebarOpen && <ListItemText primary={label} />}
              </ListItemButton>
            </Tooltip>
          </ListItem>
        ))}
      </List>

      {sidebarOpen && (
        <Box px={2} pb={2}>
          <Typography variant="caption" color="text.secondary">
            v0.1.0 — Phase 1
          </Typography>
        </Box>
      )}
    </Box>
  );

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: currentWidth,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: currentWidth,
          boxSizing: 'border-box',
          borderRight: '1px solid',
          borderColor: 'divider',
          overflowX: 'hidden',
          transition: (theme) =>
            theme.transitions.create('width', {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.standard,
            }),
        },
      }}
    >
      {drawerContent}
    </Drawer>
  );
}
