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
import PaletteIcon from '@mui/icons-material/Palette';
import TuneIcon from '@mui/icons-material/Tune';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useNavigationGuardContext } from '@/context/NavigationGuardContext';
import { useLocation } from 'react-router-dom';
import { useAppContext } from '@/context/AppContext';
import { HEADER_HEIGHT, ROUTES, SIDEBAR_COLLAPSED_WIDTH, SIDEBAR_WIDTH } from '@/utils/constants';
import { SETTINGS_SECTION_ITEMS } from '@/utils/settingsSections';
import { useActiveScrollSection } from '@/hooks/useActiveScrollSection';

const NAV_ITEMS = [
  { label: 'Home', icon: <HomeIcon />, path: ROUTES.HOME },
  { label: 'Single Review', icon: <RuleIcon />, path: ROUTES.REVIEW_REQUIREMENT },
  { label: 'Delta Review', icon: <CompareArrowsIcon />, path: ROUTES.REVIEW_DELTA },
  { label: 'Review History', icon: <HistoryIcon />, path: ROUTES.REVIEW_HISTORY },
  { label: 'Standards', icon: <MenuBookIcon />, path: ROUTES.STANDARDS },
] as const;

const BOTTOM_ITEMS = [
  { label: 'Launchpad', icon: <RocketLaunchIcon />, path: ROUTES.LANDING },
] as const;

const LABEL_ANIMATION_MS = 220;

export function Sidebar() {
  const { sidebarOpen, setSidebarOpen } = useAppContext();
  const { guardedNavigate } = useNavigationGuardContext();
  const location = useLocation();
  const isSettingsPage = location.pathname === ROUTES.SETTINGS;
  const currentWidth = sidebarOpen ? SIDEBAR_WIDTH : SIDEBAR_COLLAPSED_WIDTH;

  const SECTION_IDS = SETTINGS_SECTION_ITEMS.map((s) => s.id) as readonly string[];
  const [activeSettingsSection, setSettingsTarget] = useActiveScrollSection(
    SECTION_IDS,
    isSettingsPage,
    SETTINGS_SECTION_ITEMS[0].id,
  );

  const scrollToSettingsSection = (sectionId: string) => {
    setSettingsTarget(sectionId); // lock the highlight immediately, suppress scroll events
    const section = document.getElementById(sectionId);
    if (!section) return;
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const settingsSectionIcons: Record<string, JSX.Element> = {
    'theme-mode': <PaletteIcon />,
    'startup-behavior': <TuneIcon />,
    'review-notifications': <NotificationsActiveIcon />,
    'reset-personalization': <RestartAltIcon />,
  };

  const drawerContent = (
    <Box display="flex" flexDirection="column" height="100%">
      <List sx={{ flexGrow: 1, pt: 1 }}>
        {isSettingsPage
          ? SETTINGS_SECTION_ITEMS.map((item) => (
              <ListItem key={item.id} disablePadding>
                <Tooltip title={sidebarOpen ? '' : item.label} placement="right">
                  <ListItemButton
                    selected={activeSettingsSection === item.id}
                    onClick={() => scrollToSettingsSection(item.id)}
                    sx={{
                      mx: 1,
                      my: 0.5,
                      px: sidebarOpen ? 1.5 : 1.25,
                      justifyContent: sidebarOpen ? 'flex-start' : 'center',
                      borderRadius: 1.5,
                      position: 'relative',
                      overflow: 'hidden',
                      transition: (theme) =>
                        theme.transitions.create(['background-color', 'transform', 'padding'], {
                          duration: LABEL_ANIMATION_MS,
                          easing: theme.transitions.easing.easeInOut,
                        }),
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
                    <ListItemIcon
                      sx={(theme) => ({
                        minWidth: sidebarOpen ? 36 : 0,
                        mr: sidebarOpen ? 1 : 0,
                        justifyContent: 'center',
                        transition: theme.transitions.create(['min-width', 'margin-right'], {
                          duration: LABEL_ANIMATION_MS,
                          easing: theme.transitions.easing.easeInOut,
                        }),
                      })}
                    >
                      {settingsSectionIcons[item.id]}
                    </ListItemIcon>
                    <ListItemText
                      primary={item.label}
                      primaryTypographyProps={{ noWrap: true }}
                      sx={(theme) => ({
                        m: 0,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        maxWidth: sidebarOpen ? 200 : 0,
                        opacity: sidebarOpen ? 1 : 0,
                        transform: sidebarOpen ? 'translateX(0)' : 'translateX(-6px)',
                        transition: theme.transitions.create(
                          ['max-width', 'opacity', 'transform'],
                          {
                            duration: LABEL_ANIMATION_MS,
                            easing: theme.transitions.easing.easeInOut,
                          }
                        ),
                      })}
                    />
                  </ListItemButton>
                </Tooltip>
              </ListItem>
            ))
          : NAV_ITEMS.map(({ label, icon, path }) => (
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
                      transition: (theme) =>
                        theme.transitions.create(['background-color', 'transform', 'padding'], {
                          duration: LABEL_ANIMATION_MS,
                          easing: theme.transitions.easing.easeInOut,
                        }),
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
                    <ListItemIcon
                      sx={(theme) => ({
                        minWidth: sidebarOpen ? 36 : 0,
                        mr: sidebarOpen ? 1 : 0,
                        justifyContent: 'center',
                        transition: theme.transitions.create(['min-width', 'margin-right'], {
                          duration: LABEL_ANIMATION_MS,
                          easing: theme.transitions.easing.easeInOut,
                        }),
                      })}
                    >
                      {icon}
                    </ListItemIcon>
                    <ListItemText
                      primary={label}
                      primaryTypographyProps={{ noWrap: true }}
                      sx={(theme) => ({
                        m: 0,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        maxWidth: sidebarOpen ? 200 : 0,
                        opacity: sidebarOpen ? 1 : 0,
                        transform: sidebarOpen ? 'translateX(0)' : 'translateX(-6px)',
                        transition: theme.transitions.create(
                          ['max-width', 'opacity', 'transform'],
                          {
                            duration: LABEL_ANIMATION_MS,
                            easing: theme.transitions.easing.easeInOut,
                          }
                        ),
                      })}
                    />
                  </ListItemButton>
                </Tooltip>
              </ListItem>
            ))}
      </List>

      {!isSettingsPage && (
        <>
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
                      my: 0.5,
                      px: sidebarOpen ? 1.5 : 1.25,
                      justifyContent: sidebarOpen ? 'flex-start' : 'center',
                      borderRadius: 1.5,
                      overflow: 'hidden',
                      transition: (theme) =>
                        theme.transitions.create(['padding'], {
                          duration: LABEL_ANIMATION_MS,
                          easing: theme.transitions.easing.easeInOut,
                        }),
                    }}
                  >
                    <ListItemIcon
                      sx={(theme) => ({
                        minWidth: sidebarOpen ? 36 : 0,
                        mr: sidebarOpen ? 1 : 0,
                        justifyContent: 'center',
                        transition: theme.transitions.create(['min-width', 'margin-right'], {
                          duration: LABEL_ANIMATION_MS,
                          easing: theme.transitions.easing.easeInOut,
                        }),
                      })}
                    >
                      {icon}
                    </ListItemIcon>
                    <ListItemText
                      primary={label}
                      primaryTypographyProps={{ noWrap: true }}
                      sx={(theme) => ({
                        m: 0,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        maxWidth: sidebarOpen ? 200 : 0,
                        opacity: sidebarOpen ? 1 : 0,
                        transform: sidebarOpen ? 'translateX(0)' : 'translateX(-6px)',
                        transition: theme.transitions.create(
                          ['max-width', 'opacity', 'transform'],
                          {
                            duration: LABEL_ANIMATION_MS,
                            easing: theme.transitions.easing.easeInOut,
                          }
                        ),
                      })}
                    />
                  </ListItemButton>
                </Tooltip>
              </ListItem>
            ))}
          </List>
        </>
      )}

      <Box
        px={2}
        pb={2}
        sx={(theme) => ({
          overflow: 'hidden',
          maxHeight: sidebarOpen ? 28 : 0,
          opacity: sidebarOpen ? 1 : 0,
          transition: theme.transitions.create(['max-height', 'opacity'], {
            duration: LABEL_ANIMATION_MS,
            easing: theme.transitions.easing.easeInOut,
          }),
        })}
      >
        <Typography variant="caption" color="text.secondary" noWrap>
          v0.1.0 - Phase 2
        </Typography>
      </Box>
    </Box>
  );

  return (
    /* Wrapper positions the Drawer + the edge toggle button together */
    <Box
      sx={{
        position: 'fixed',
        top: `${HEADER_HEIGHT}px`,
        left: 0,
        height: `calc(100% - ${HEADER_HEIGHT}px)`,
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
