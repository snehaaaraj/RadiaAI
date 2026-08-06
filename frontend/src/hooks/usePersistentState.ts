import { useEffect, useState } from 'react';

type StorageKind = 'local' | 'session';

interface UsePersistentStateOptions<T> {
  key: string;
  initialValue: T;
  storage?: StorageKind;
}

function getStorage(storage: StorageKind): Storage {
  return storage === 'session' ? window.sessionStorage : window.localStorage;
}

export function usePersistentState<T>({
  key,
  initialValue,
  storage = 'local',
}: UsePersistentStateOptions<T>) {
  const [state, setState] = useState<T>(() => {
    if (typeof window === 'undefined') return initialValue;
    try {
      const raw = getStorage(storage).getItem(key);
      if (raw == null) return initialValue;
      return JSON.parse(raw) as T;
    } catch (error) {
      console.warn(`Failed to load persisted state for key "${key}"`, error);
      return initialValue;
    }
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      getStorage(storage).setItem(key, JSON.stringify(state));
    } catch (error) {
      console.warn(`Failed to persist state for key "${key}"`, error);
    }
  }, [key, state, storage]);

  const clear = () => {
    if (typeof window !== 'undefined') {
      getStorage(storage).removeItem(key);
    }
    setState(initialValue);
  };

  return { state, setState, clear };
}
