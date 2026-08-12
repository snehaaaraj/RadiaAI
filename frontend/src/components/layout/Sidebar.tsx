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
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import HistoryIcon from '@mui/icons-material/History';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import SettingsIcon from '@mui/icons-material/Settings';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useNavigationGuardContext } from '@/context/NavigationGuardContext';
import { useLocation } from 'react-router-dom';
import { useAppContext } from '@/context/AppContext';
import { ROUTES, SIDEBAR_COLLAPSED_WIDTH, SIDEBAR_WIDTH } from '@/utils/constants';

const NAV_ITEMS = [
  { label: 'Home', icon: <HomeIcon />, path: ROUTES.HOME },
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
  const { guardedNavigate } = useNavigationGuardContext();
  const location = useLocation();
  const currentWidth = sidebarOpen ? SIDEBAR_WIDTH : SIDEBAR_COLLAPSED_WIDTH;

  const drawerContent = (
    <Box display="flex" flexDirection="column" height="100%">
      <List sx={{ flexGrow: 1, pt: 1 }}>
        {NAV_ITEMS.map(({ label, icon, path }) => (
          <ListItem key={path} disablePadding>
            <Tooltip title={sidebarOpen ? '' : label} placement="right">
              <ListItemButton
                selected={location.pathname === path}
                onClick={() => guardedNavigate(path)}
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
                onClick={() => guardedNavigate(path)}
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
            v0.1.0 - Phase 2
          </Typography>
        </Box>
      )}
    </Box>
  );

  return (
    /* Wrapper positions the Drawer + the edge toggle button together */
    <Box
      sx={{
        position: 'fixed',
        top: '64px',
        left: 0,
        height: 'calc(100% - 64px)',
        width: currentWidth,
        transition: (theme) =>
          theme.transitions.create('width', {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.standard,
          }),
        zIndex: (theme) => theme.zIndex.drawer,
        flexShrink: 0,
      }}
    >
      <Drawer
        variant="permanent"
        sx={{
          width: '100%',
          height: '100%',
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: '100%',
            boxSizing: 'border-box',
            borderRight: '1px solid',
            borderColor: 'divider',
            overflowX: 'hidden',
            position: 'relative',
            top: 'unset',
            height: '100%',
          },
        }}
      >
        {drawerContent}
      </Drawer>

      {/* Edge collapse/expand arrow — sits on the right border of the sidebar */}
      <Tooltip title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'} placement="right">
        <IconButton
          size="small"
          aria-label="toggle sidebar"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          sx={{
            position: 'absolute',
            top: '50%',
            right: -12,
            transform: 'translateY(-50%)',
            zIndex: (theme) => theme.zIndex.drawer + 1,
            width: 24,
            height: 24,
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
            boxShadow: 2,
            '&:hover': {
              bgcolor: 'action.hover',
            },
          }}
        >
          {sidebarOpen ? (
            <ChevronLeftIcon sx={{ fontSize: 16 }} />
          ) : (
            <ChevronRightIcon sx={{ fontSize: 16 }} />
          )}
        </IconButton>
      </Tooltip>
    </Box>
  );
}
