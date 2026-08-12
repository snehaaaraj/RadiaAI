import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { CssBaseline, Stack, ThemeProvider, Typography } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { AnimatePresence, motion } from 'framer-motion';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { AppProvider, useAppContext } from '@/context/AppContext';
import Landing from '@/pages/Landing';
import Home from '@/pages/Home';
import RequirementReview from '@/pages/RequirementReview';
import DeltaReview from '@/pages/DeltaReview';
import ReviewHistory from '@/pages/ReviewHistory';
import Standards from '@/pages/Standards';
import Chat from '@/pages/Chat';
import Search from '@/pages/Search';
import Documents from '@/pages/Documents';
import Settings from '@/pages/Settings';
import { createAppTheme } from '@/theme';
import { ROUTES } from '@/utils/constants';
import useMediaQuery from '@mui/material/useMediaQuery';

const lightLogoUrl = new URL('./assets/radia-circle-white background.png', import.meta.url).href;
const darkLogoUrl = new URL('./assets/radia-circle-white lines.jpg', import.meta.url).href;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
    mutations: {
      retry: 0,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppProvider>
        <ThemeShell>
          <BrowserRouter>
            <StartupSplash />
            <Routes>
              <Route path={ROUTES.LANDING} element={<Landing />} />
              <Route element={<AppLayout />}>
                <Route path={ROUTES.HOME} element={<Home />} />
                <Route path={ROUTES.REVIEW_REQUIREMENT} element={<RequirementReview />} />
                <Route path={ROUTES.REVIEW_DELTA} element={<DeltaReview />} />
                <Route path={ROUTES.REVIEW_HISTORY} element={<ReviewHistory />} />
                <Route path={ROUTES.STANDARDS} element={<Standards />} />
                <Route path={ROUTES.CHAT} element={<Chat />} />
                <Route path={ROUTES.SEARCH} element={<Search />} />
                <Route path={ROUTES.DOCUMENTS} element={<Documents />} />
                <Route path={ROUTES.SETTINGS} element={<Settings />} />
              </Route>
              <Route path="*" element={<Navigate to={ROUTES.LANDING} replace />} />
            </Routes>
          </BrowserRouter>
        </ThemeShell>
      </AppProvider>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}

function ThemeShell({ children }: { children: ReactNode }) {
  const { themePreference, accentColor, uiDensity } = useAppContext();
  const prefersDark = useMediaQuery('(prefers-color-scheme: dark)', { noSsr: true });
  const mode = themePreference === 'system' ? (prefersDark ? 'dark' : 'light') : themePreference;

  const theme = useMemo(() => createAppTheme(mode, accentColor, uiDensity), [mode, accentColor, uiDensity]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}

function StartupSplash() {
  const theme = useTheme();
  const [visible, setVisible] = useState(true);
  const logoSrc = theme.palette.mode === 'dark' ? darkLogoUrl : lightLogoUrl;

  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(false), 1700);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ y: 0, opacity: 1 }}
          animate={{ y: '-100%', opacity: 1 }}
          exit={{ y: '-100%', opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.9, ease: [0.22, 1, 0.36, 1] }}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 4000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundImage: `linear-gradient(135deg, #2F4659 0%, #142032 100%), url("${logoSrc}")`,
            backgroundSize: 'cover, min(56vw, 620px)',
            backgroundRepeat: 'no-repeat, no-repeat',
            backgroundPosition: 'center, center',
            color: '#FFFFFF',
          }}
        >
          <Stack direction="row" spacing={1.25} alignItems="center">
            <Typography variant="h3" fontWeight={900} letterSpacing={1.2}>
              Radia AI
            </Typography>
          </Stack>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
