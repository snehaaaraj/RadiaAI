import { useContext } from 'react';
import { NavigationGuardContext, type NavigationGuardContextValue } from './NavigationGuardContext';

export function useNavigationGuardContext(): NavigationGuardContextValue {
  const ctx = useContext(NavigationGuardContext);
  if (!ctx) throw new Error('useNavigationGuardContext must be used inside NavigationGuardProvider');
  return ctx;
}
