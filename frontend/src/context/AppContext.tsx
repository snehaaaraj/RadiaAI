/**
 * Application context — global state that needs to be accessible
 * across multiple pages without prop drilling.
 *
 * Intentionally minimal in Phase 1. Phase 2 will add auth state (user, token).
 */

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ROUTES } from '@/utils/constants';

export type ThemePreference = 'light' | 'dark' | 'system';
export type AccentColor = 'indigo' | 'violet' | 'teal' | 'rose';
export type UiDensity = 'comfortable' | 'compact';
export type MotionPreference = 'full' | 'reduced';
export type WorkspaceStartPage =
  | typeof ROUTES.HOME
  | typeof ROUTES.REVIEW_REQUIREMENT_SET
  | typeof ROUTES.REVIEW_REQUIREMENT
  | typeof ROUTES.REVIEW_DELTA
  | typeof ROUTES.REVIEW_HISTORY
  | typeof ROUTES.STANDARDS
  | typeof ROUTES.SEARCH
  | typeof ROUTES.CHAT
  | typeof ROUTES.DOCUMENTS;

const PREFS_STORAGE_KEY = 'radia-ui-preferences';
const SIDEBAR_STORAGE_KEY = 'radia-sidebar-open';

interface StoredPreferences {
  themePreference: ThemePreference;
  accentColor: AccentColor;
  uiDensity: UiDensity;
  motionPreference: MotionPreference;
  defaultWorkspaceRoute: WorkspaceStartPage;
}

const DEFAULT_PREFERENCES: StoredPreferences = {
  themePreference: 'system',
  accentColor: 'indigo',
  uiDensity: 'comfortable',
  motionPreference: 'full',
  defaultWorkspaceRoute: ROUTES.HOME,
};
const WORKSPACE_ROUTES: WorkspaceStartPage[] = [
  ROUTES.HOME,
  ROUTES.REVIEW_REQUIREMENT_SET,
  ROUTES.REVIEW_REQUIREMENT,
  ROUTES.REVIEW_DELTA,
  ROUTES.REVIEW_HISTORY,
  ROUTES.STANDARDS,
  ROUTES.SEARCH,
  ROUTES.CHAT,
  ROUTES.DOCUMENTS,
];

interface AppContextValue {
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  themePreference: ThemePreference;
  setThemePreference: (theme: ThemePreference) => void;
  accentColor: AccentColor;
  setAccentColor: (color: AccentColor) => void;
  uiDensity: UiDensity;
  setUiDensity: (density: UiDensity) => void;
  motionPreference: MotionPreference;
  setMotionPreference: (motion: MotionPreference) => void;
  defaultWorkspaceRoute: WorkspaceStartPage;
  setDefaultWorkspaceRoute: (path: WorkspaceStartPage) => void;
  resetPersonalization: () => void;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpenState] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true;
    const stored = window.localStorage.getItem(SIDEBAR_STORAGE_KEY);
    return stored == null ? true : stored === 'true';
  });

  const [preferences, setPreferences] = useState<StoredPreferences>(() => {
    if (typeof window === 'undefined') return DEFAULT_PREFERENCES;
    const storedRaw = window.localStorage.getItem(PREFS_STORAGE_KEY);
    if (!storedRaw) return DEFAULT_PREFERENCES;
    try {
      const parsed = JSON.parse(storedRaw) as Partial<StoredPreferences>;
      const merged: StoredPreferences = {
        ...DEFAULT_PREFERENCES,
        ...parsed,
      };
      if (!WORKSPACE_ROUTES.includes(merged.defaultWorkspaceRoute)) {
        return DEFAULT_PREFERENCES;
      }
      return merged;
    } catch {
      return DEFAULT_PREFERENCES;
    }
  });

  const setSidebarOpen = (open: boolean) => {
    setSidebarOpenState(open);
  };

  const setThemePreference = (theme: ThemePreference) => {
    setPreferences((prev) => ({ ...prev, themePreference: theme }));
  };

  const setAccentColor = (color: AccentColor) => {
    setPreferences((prev) => ({ ...prev, accentColor: color }));
  };

  const setUiDensity = (density: UiDensity) => {
    setPreferences((prev) => ({ ...prev, uiDensity: density }));
  };

  const setMotionPreference = (motion: MotionPreference) => {
    setPreferences((prev) => ({ ...prev, motionPreference: motion }));
  };

  const setDefaultWorkspaceRoute = (path: WorkspaceStartPage) => {
    setPreferences((prev) => ({ ...prev, defaultWorkspaceRoute: path }));
  };

  const resetPersonalization = () => {
    setPreferences(DEFAULT_PREFERENCES);
    setSidebarOpenState(true);
  };

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(PREFS_STORAGE_KEY, JSON.stringify(preferences));
    }
  }, [preferences]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(sidebarOpen));
    }
  }, [sidebarOpen]);

  const value = useMemo<AppContextValue>(
    () => ({
      sidebarOpen,
      setSidebarOpen,
      themePreference: preferences.themePreference,
      setThemePreference,
      accentColor: preferences.accentColor,
      setAccentColor,
      uiDensity: preferences.uiDensity,
      setUiDensity,
      motionPreference: preferences.motionPreference,
      setMotionPreference,
      defaultWorkspaceRoute: preferences.defaultWorkspaceRoute,
      setDefaultWorkspaceRoute,
      resetPersonalization,
    }),
    [sidebarOpen, preferences]
  );

  return (
    <AppContext.Provider value={value}>{children}</AppContext.Provider>
  );
}

export function useAppContext(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppContext must be used inside AppProvider');
  return ctx;
}
