import { useContext } from 'react';
import { AppContext, type AppContextValue } from './AppContext';

export function useAppContext(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppContext must be used inside AppProvider');
  return ctx;
}
