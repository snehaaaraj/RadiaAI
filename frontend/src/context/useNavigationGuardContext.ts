import { createContext, useContext } from 'react';
import type { NavigationGuardContextValue } from './NavigationGuardContext';

export const NavigationGuardContext = createContext<NavigationGuardContextValue | null>(null);

export function useNavigationGuardContext(): NavigationGuardContextValue {
  const ctx = useContext(NavigationGuardContext);
  if (!ctx) throw new Error('useNavigationGuardContext must be used inside NavigationGuardProvider');
  return ctx;
}
