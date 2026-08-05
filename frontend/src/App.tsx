import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { CssBaseline, ThemeProvider } from '@mui/material';
import { useMemo, type ReactNode } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { AppProvider, useAppContext } from '@/context/AppContext';
import Home from '@/pages/Home';
import RequirementSetReview from '@/pages/RequirementSetReview';
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
            <Routes>
              <Route element={<AppLayout />}>
                <Route path={ROUTES.HOME} element={<Home />} />
                <Route path={ROUTES.REVIEW_REQUIREMENT_SET} element={<RequirementSetReview />} />
                <Route path={ROUTES.REVIEW_REQUIREMENT} element={<RequirementReview />} />
                <Route path={ROUTES.REVIEW_DELTA} element={<DeltaReview />} />
                <Route path={ROUTES.REVIEW_HISTORY} element={<ReviewHistory />} />
                <Route path={ROUTES.STANDARDS} element={<Standards />} />
                <Route path={ROUTES.CHAT} element={<Chat />} />
                <Route path={ROUTES.SEARCH} element={<Search />} />
                <Route path={ROUTES.DOCUMENTS} element={<Documents />} />
                <Route path={ROUTES.SETTINGS} element={<Settings />} />
                {/* Catch-all redirect to home */}
                <Route path="*" element={<Navigate to={ROUTES.HOME} replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </ThemeShell>
      </AppProvider>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}

function ThemeShell({ children }: { children: ReactNode }) {
  const { themePreference } = useAppContext();
  const prefersDark = useMediaQuery('(prefers-color-scheme: dark)', { noSsr: true });
  const mode = themePreference === 'system' ? (prefersDark ? 'dark' : 'light') : themePreference;

  const theme = useMemo(() => createAppTheme(mode), [mode]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}
