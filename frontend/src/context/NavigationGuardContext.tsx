import { createContext, useCallback, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';

export interface NavigationGuardContextValue {
  /** Pages call this to register whether they have unsaved/in-progress state */
  setDirty: (dirty: boolean) => void;
  /** Sidebar / any nav component calls this instead of navigate() directly */
  guardedNavigate: (path: string) => void;
  /** Dialog state — consumed by the single dialog rendered in AppLayout */
  dialogOpen: boolean;
  handleConfirm: () => void;
  handleCancel: () => void;
}

export const NavigationGuardContext = createContext<NavigationGuardContextValue | null>(null);

export function NavigationGuardProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const isDirtyRef = useRef(false);
  const pendingPath = useRef<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const setDirty = useCallback((dirty: boolean) => {
    isDirtyRef.current = dirty;
  }, []);

  const guardedNavigate = useCallback((path: string) => {
    if (isDirtyRef.current) {
      pendingPath.current = path;
      setDialogOpen(true);
    } else {
      navigate(path);
    }
  }, [navigate]);

  const handleConfirm = useCallback(() => {
    isDirtyRef.current = false;
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

  return (
    <NavigationGuardContext.Provider value={{ setDirty, guardedNavigate, dialogOpen, handleConfirm, handleCancel }}>
      {children}
    </NavigationGuardContext.Provider>
  );
}
