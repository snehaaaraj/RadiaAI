import Box from '@mui/material/Box';
import Toolbar from '@mui/material/Toolbar';
import { AnimatePresence, motion } from 'framer-motion';
import { Outlet, useLocation } from 'react-router-dom';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';
import { NavigationConfirmDialog } from '@/components/common/NavigationConfirmDialog';
import { NavigationGuardProvider, useNavigationGuardContext } from '@/context/NavigationGuardContext';
import { useAppContext } from '@/context/AppContext';
import { SIDEBAR_COLLAPSED_WIDTH, SIDEBAR_WIDTH } from '@/utils/constants';

function AppLayoutInner() {
  const { sidebarOpen, motionPreference, uiDensity } = useAppContext();
  const location = useLocation();
  const sidebarWidth = sidebarOpen ? SIDEBAR_WIDTH : SIDEBAR_COLLAPSED_WIDTH;
  const { dialogOpen, handleConfirm, handleCancel } = useNavigationGuardContext();

  return (
    <Box display="flex">
      <TopBar />
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
          marginLeft: 0,
          width: `calc(100% - ${sidebarWidth}px)`,
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

      <NavigationConfirmDialog
        open={dialogOpen}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    </Box>
  );
}

/**
 * Root layout wrapper — renders TopBar + Sidebar + page content (via Outlet).
 * All authenticated pages are rendered inside this layout.
 */
export function AppLayout() {
  return (
    <NavigationGuardProvider>
      <AppLayoutInner />
    </NavigationGuardProvider>
  );
}
