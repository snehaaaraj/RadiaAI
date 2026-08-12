import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { Box, CssBaseline, Stack, ThemeProvider, Typography } from '@mui/material';
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

const BRAND_BARS = [
  { right: '8%', bottom: '18%', w: 132, rotate: -40 },
  { right: '16%', bottom: '23%', w: 98, rotate: -55 },
  { right: '4%', bottom: '30%', w: 106, rotate: -12 },
  { right: '14%', bottom: '35%', w: 116, rotate: -28 },
  { right: '1%', bottom: '42%', w: 92, rotate: 0 },
  { right: '9%', bottom: '47%', w: 88, rotate: -18 },
] as const;

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
  const [visible, setVisible] = useState(true);

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
            background: 'linear-gradient(135deg, #2F4659 0%, #142032 100%)',
            color: '#FFFFFF',
          }}
        >
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              background:
                'radial-gradient(circle at 18% 22%, rgba(102, 141, 182, 0.34) 0%, rgba(102, 141, 182, 0) 34%)',
            }}
          />
          {BRAND_BARS.map((bar, index) => (
            <Box
              key={`${bar.right}-${bar.bottom}-${index}`}
              sx={{
                position: 'absolute',
                right: bar.right,
                bottom: bar.bottom,
                width: { xs: Math.round(bar.w * 0.72), md: bar.w },
                height: { xs: 22, md: 28 },
                borderRadius: 1,
                bgcolor: '#C6D1DE',
                opacity: 0.62,
                transform: `rotate(${bar.rotate}deg)`,
              }}
            />
          ))}
          <Typography
            sx={{
              position: 'absolute',
              top: { xs: 34, md: 42 },
              left: { xs: 24, md: 32 },
              fontWeight: 900,
              letterSpacing: 1.2,
              fontSize: { xs: '2rem', md: '2.8rem' },
              color: '#D9E4F0',
            }}
          >
            RADIA
          </Typography>
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
