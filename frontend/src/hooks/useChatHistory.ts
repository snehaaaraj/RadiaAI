import { useCallback, useEffect, useRef, useSyncExternalStore, type SetStateAction } from 'react';
import { useCurrentUser } from '@/hooks/useCurrentUser';
import type { ChatMessage } from '@/types/api';

const EMPTY: ChatMessage[] = [];
const cache = new Map<string, ChatMessage[]>();
const listeners = new Set<() => void>();

function isChatHistory(value: unknown): value is ChatMessage[] {
  return Array.isArray(value) && value.every(
    (turn: unknown) => typeof turn === 'object' && turn !== null &&
      'role' in turn && (turn.role === 'user' || turn.role === 'assistant') &&
      'content' in turn && typeof turn.content === 'string'
  );
}

function readStored(storageKey: string): ChatMessage[] | null {
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!isChatHistory(parsed)) throw new Error('Invalid chat history format');
    return parsed;
  } catch (error) {
    console.error('Unable to load chat history', error);
    return null;
  }
}

function persist(key: string, history: ChatMessage[]) {
  try {
    window.localStorage.setItem(key, JSON.stringify(history));
  } catch (error) {
    console.error('Unable to save chat history', error);
  }
}

/** Fold the former separate page and pop-up histories into the shared conversation once. */
function migrateLegacy(key: string, scope: string): ChatMessage[] {
  const legacyKeys = [`radia-chat-page-history:${scope}`, `radia-chat-widget-history:${scope}`];
  const merged = legacyKeys.flatMap((legacyKey) => readStored(legacyKey) ?? []);
  if (merged.length > 0) persist(key, merged);
  for (const legacyKey of legacyKeys) {
    try {
      window.localStorage.removeItem(legacyKey);
    } catch {
      // Leaving a stale legacy entry behind is harmless once the shared key exists.
    }
  }
  return merged;
}

function load(key: string, scope: string): ChatMessage[] {
  const cached = cache.get(key);
  if (cached) return cached;
  if (typeof window === 'undefined') return EMPTY;
  const history = window.localStorage.getItem(key) === null
    ? migrateLegacy(key, scope)
    : readStored(key) ?? [];
  cache.set(key, history);
  return history;
}

function emit() {
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  // Keep other open tabs in sync with the same user's conversation.
  const onStorage = (event: StorageEvent) => {
    if (event.key?.startsWith('radia-chat-history:')) {
      cache.delete(event.key);
      listener();
    }
  };
  window.addEventListener('storage', onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener('storage', onStorage);
  };
}

/** Clears the in-memory store; intended for tests. */
export function resetChatHistoryCache() {
  cache.clear();
}

/**
 * One browser-local conversation shared by the chat page and the pop-up, scoped to the
 * API-verified tenant and user (never their role).
 */
export function useChatHistory() {
  const { data: user } = useCurrentUser();
  const scope = user
    ? `${encodeURIComponent(user.tenant_id)}:${encodeURIComponent(user.user_id)}`
    : null;
  const key = scope ? `radia-chat-history:${scope}` : null;

  const history = useSyncExternalStore(
    subscribe,
    () => (key && scope ? load(key, scope) : EMPTY),
    () => EMPTY
  );

  const activeKey = useRef(key);
  useEffect(() => {
    activeKey.current = key;
  }, [key]);

  const setHistory = useCallback((update: SetStateAction<ChatMessage[]>) => {
    if (!key || !scope) return;
    // Ignore a response that arrives after its owner has changed.
    if (activeKey.current !== key) return;
    const previous = load(key, scope);
    const next = typeof update === 'function' ? update(previous) : update;
    cache.set(key, next);
    persist(key, next);
    emit();
  }, [key, scope]);
  const clearHistory = useCallback(() => setHistory([]), [setHistory]);

  return { history, setHistory, clearHistory };
}
