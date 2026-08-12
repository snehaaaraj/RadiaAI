import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useBeforeUnload } from 'react-router-dom';

/**
 * Intercepts in-app navigation and browser tab close/refresh when `isDirty` is true.
 * Returns a `guardedNavigate` function to use in place of `navigate`, and dialog
 * state so the caller can render a confirmation dialog.
 */
export function useNavigationGuard(isDirty: boolean) {
  const navigate = useNavigate();
  const [dialogOpen, setDialogOpen] = useState(false);
  const pendingPath = useRef<string | null>(null);

  // Block browser tab close / hard refresh when dirty
  useBeforeUnload(
    useCallback(
      (e: BeforeUnloadEvent) => {
        if (isDirty) {
          e.preventDefault();
        }
      },
      [isDirty]
    )
  );

  // Reset pending path whenever dirty state is cleared
  useEffect(() => {
    if (!isDirty) {
      pendingPath.current = null;
    }
  }, [isDirty]);

  /** Call this instead of `navigate(path)` from nav items / buttons */
  const guardedNavigate = useCallback(
    (path: string) => {
      if (isDirty) {
        pendingPath.current = path;
        setDialogOpen(true);
      } else {
        navigate(path);
      }
    },
    [isDirty, navigate]
  );

  const handleConfirm = useCallback(() => {
    setDialogOpen(false);
    if (pendingPath.current) {
      navigate(pendingPath.current);
      pendingPath.current = null;
    }
  }, [navigate]);

  const handleCancel = useCallback(() => {
    setDialogOpen(false);
    pendingPath.current = null;
  }, []);

  return { guardedNavigate, dialogOpen, handleConfirm, handleCancel };
}
