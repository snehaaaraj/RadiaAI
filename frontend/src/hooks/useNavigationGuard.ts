import { useEffect } from 'react';
import { useBeforeUnload } from 'react-router-dom';
import { useNavigationGuardContext } from '@/context/NavigationGuardContext';

/**
 * Call this in a page component to register whether it has unsaved/in-progress state.
 * When dirty, the global NavigationGuardContext will intercept sidebar navigation
 * and show a confirmation dialog before leaving.
 */
export function useNavigationGuard(isDirty: boolean) {
  const { setDirty } = useNavigationGuardContext();

  // Keep context in sync whenever isDirty changes
  useEffect(() => {
    setDirty(isDirty);
    // Clear on unmount (user navigated away after confirming)
    return () => setDirty(false);
  }, [isDirty, setDirty]);

  // Also block browser tab close / hard refresh
  useBeforeUnload(
    (e: BeforeUnloadEvent) => {
      if (isDirty) e.preventDefault();
    }
  );
}
