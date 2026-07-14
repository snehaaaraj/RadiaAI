import Box from '@mui/material/Box';
import Toolbar from '@mui/material/Toolbar';
import { Outlet } from 'react-router-dom';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';
import { useAppContext } from '@/context/AppContext';

const DRAWER_WIDTH = 240;

/**
 * Root layout wrapper — renders TopBar + Sidebar + page content (via Outlet).
 * All authenticated pages are rendered inside this layout.
 */
export function AppLayout() {
  const { sidebarOpen } = useAppContext();

  return (
    <Box display="flex">
      <TopBar drawerWidth={DRAWER_WIDTH} />
      <Sidebar />

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          transition: (t) =>
            t.transitions.create('margin', {
              easing: t.transitions.easing.sharp,
              duration: t.transitions.duration.leavingScreen,
            }),
          marginLeft: sidebarOpen ? 0 : `-${DRAWER_WIDTH}px`,
          minHeight: '100vh',
          bgcolor: 'background.default',
        }}
      >
        {/* Push content below the AppBar */}
        <Toolbar />
        <Outlet />
      </Box>
    </Box>
  );
}
