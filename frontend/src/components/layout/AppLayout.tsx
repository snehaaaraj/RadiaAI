import Box from '@mui/material/Box';
import Toolbar from '@mui/material/Toolbar';
import { AnimatePresence, motion } from 'framer-motion';
import { Outlet, useLocation } from 'react-router-dom';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';
import { useAppContext } from '@/context/AppContext';

const DRAWER_WIDTH = 240;

/**
 * Root layout wrapper — renders TopBar + Sidebar + page content (via Outlet).
 * All authenticated pages are rendered inside this layout.
 */
export function AppLayout() {
  const { sidebarOpen, motionPreference, uiDensity } = useAppContext();
  const location = useLocation();

  return (
    <Box display="flex">
      <TopBar drawerWidth={DRAWER_WIDTH} />
      <Sidebar />

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          transition: (t) =>
            t.transitions.create('margin', {
              easing: t.transitions.easing.sharp,
              duration: t.transitions.duration.leavingScreen,
            }),
          marginLeft: sidebarOpen ? 0 : `-${DRAWER_WIDTH}px`,
          minHeight: '100vh',
          bgcolor: 'background.default',
          p: uiDensity === 'compact' ? 2 : 3,
        }}
      >
        {/* Push content below the AppBar */}
        <Toolbar />
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={motionPreference === 'reduced' ? false : { opacity: 0, y: 10 }}
            animate={motionPreference === 'reduced' ? {} : { opacity: 1, y: 0 }}
            exit={motionPreference === 'reduced' ? {} : { opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </Box>
    </Box>
  );
}
