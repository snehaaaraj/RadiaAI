import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { CssBaseline, ThemeProvider } from '@mui/material';
import { useMemo, type ReactNode } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { AppProvider } from '@/context/AppContext';
import { useAppContext } from '@/context/useAppContext';
import Landing from '@/pages/Landing';
import Chat from '@/pages/Chat';
import Search from '@/pages/Search';
import Documents from '@/pages/Documents';
import Settings from '@/pages/Settings';
import Home from '@/radia_ai/features/jamaRequirementReviewer/pages/Home';
import RequirementReview from '@/radia_ai/features/jamaRequirementReviewer/pages/RequirementReview';
import DeltaReview from '@/radia_ai/features/jamaRequirementReviewer/pages/DeltaReview';
import ReviewHistory from '@/radia_ai/features/jamaRequirementReviewer/pages/ReviewHistory';
import Standards from '@/radia_ai/features/jamaRequirementReviewer/pages/Standards';
import JamaRoundtripHome from '@/radia_ai/features/jamaRoundtrip/pages/JamaRoundtripHome';
import RadiaResources from '@/radia_ai/features/resources/pages/RadiaResources';
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
              <Route path={ROUTES.LANDING} element={<Landing />} />
              <Route path={ROUTES.RADIA_AI_RESOURCES} element={<RadiaResources />} />
              <Route path={ROUTES.JAMA_ROUNDTRIP} element={<JamaRoundtripHome />} />
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
