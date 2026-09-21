import Box from '@mui/material/Box';
import Toolbar from '@mui/material/Toolbar';
import { AnimatePresence, motion } from 'framer-motion';
import { Outlet, useLocation } from 'react-router-dom';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';
import { ChatWidget } from '@/components/chat/ChatWidget';
import { NavigationConfirmDialog } from '@/components/common/NavigationConfirmDialog';
import { NavigationGuardProvider } from '@/context/NavigationGuardContext';
import { useAppContext } from '@/context/useAppContext';
import { useNavigationGuardContext } from '@/context/useNavigationGuardContext';
import { HEADER_HEIGHT, ROUTES, SIDEBAR_COLLAPSED_WIDTH, SIDEBAR_WIDTH } from '@/utils/constants';

function AppLayoutInner() {
  const { sidebarOpen, motionPreference, uiDensity } = useAppContext();
  const location = useLocation();
  const isChatPage = location.pathname === ROUTES.CHAT;
  const sidebarWidth = isChatPage ? 0 : sidebarOpen ? SIDEBAR_WIDTH : SIDEBAR_COLLAPSED_WIDTH;
  const { dialogOpen, handleConfirm, handleCancel } = useNavigationGuardContext();

  return (
    <Box display="flex">
      <TopBar />
      {/* Chat is a standalone workspace, unrelated to the Jama review nav items - no sidebar. */}
      {!isChatPage && <Sidebar />}

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          transition: (t) =>
            t.transitions.create(['margin-left', 'width'], {
              easing: t.transitions.easing.sharp,
              duration: t.transitions.duration.standard,
            }),
          marginLeft: `${sidebarWidth}px`,
          width: `calc(100% - ${sidebarWidth}px)`,
          // The chat page manages its own internal scroll region (see Chat.tsx)
          // instead of growing the whole page - fix its height to the viewport
          // and disable the page-level scrollbar.
          height: isChatPage ? '100vh' : undefined,
          minHeight: isChatPage ? undefined : '100vh',
          overflow: isChatPage ? 'hidden' : undefined,
          bgcolor: 'background.default',
          p: uiDensity === 'compact' ? 2 : 3,
          display: isChatPage ? 'flex' : undefined,
          flexDirection: isChatPage ? 'column' : undefined,
        }}
      >
        {/* Push content below the AppBar */}
        <Toolbar sx={{ minHeight: `${HEADER_HEIGHT}px !important`, flexShrink: 0 }} />
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={motionPreference === 'reduced' ? false : { opacity: 0, y: 10 }}
            animate={motionPreference === 'reduced' ? {} : { opacity: 1, y: 0 }}
            exit={motionPreference === 'reduced' ? {} : { opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            style={isChatPage ? { flexGrow: 1, minHeight: 0, display: 'flex', flexDirection: 'column' } : undefined}
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

      {location.pathname !== ROUTES.CHAT && <ChatWidget />}
    </Box>
  );
}

/**
 * Root layout wrapper - renders TopBar + Sidebar + page content (via Outlet).
 * All authenticated pages are rendered inside this layout.
 */
export function AppLayout() {
  return (
    <NavigationGuardProvider>
      <AppLayoutInner />
    </NavigationGuardProvider>
  );
}
