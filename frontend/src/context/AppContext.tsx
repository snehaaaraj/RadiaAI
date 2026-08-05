/**
 * Application context — global state that needs to be accessible
 * across multiple pages without prop drilling.
 *
 * Intentionally minimal in Phase 1. Phase 2 will add auth state (user, token).
 */

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

export type ThemePreference = 'light' | 'dark' | 'system';

const THEME_STORAGE_KEY = 'radia-theme-preference';

interface AppContextValue {
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  themePreference: ThemePreference;
  setThemePreference: (theme: ThemePreference) => void;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [themePreference, setThemePreference] = useState<ThemePreference>(() => {
    const stored =
      typeof window !== 'undefined' ? window.localStorage.getItem(THEME_STORAGE_KEY) : null;
    return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(THEME_STORAGE_KEY, themePreference);
    }
  }, [themePreference]);

  return (
    <AppContext.Provider
      value={{ sidebarOpen, setSidebarOpen, themePreference, setThemePreference }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppContext must be used inside AppProvider');
  return ctx;
}
