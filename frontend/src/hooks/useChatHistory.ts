import { useCallback, useEffect, useState, type SetStateAction } from 'react';
import { useCurrentUser } from '@/hooks/useCurrentUser';
import type { ChatMessage } from '@/types/api';

function loadHistory(key: string | null): ChatMessage[] {
  if (!key || typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed) || !parsed.every(
      (turn: unknown) => typeof turn === 'object' && turn !== null &&
        'role' in turn && (turn.role === 'user' || turn.role === 'assistant') &&
        'content' in turn && typeof turn.content === 'string'
    )) {
      throw new Error('Invalid chat history format');
    }
    return parsed;
  } catch (error) {
    console.error('Unable to load chat history', error);
    return [];
  }
}

/** Browser-local conversations are scoped to the API-verified tenant and user, never their role. */
export function useChatHistory(surface: 'page' | 'widget') {
  const { data: user } = useCurrentUser();
  const key = user
    ? `radia-chat-${surface}-history:${encodeURIComponent(user.tenant_id)}:${encodeURIComponent(user.user_id)}`
    : null;
  const [state, setState] = useState(() => ({ key, history: loadHistory(key) }));

  if (state.key !== key) {
    setState({ key, history: loadHistory(key) });
  }

  useEffect(() => {
    if (!state.key || typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(state.key, JSON.stringify(state.history));
    } catch (error) {
      console.error('Unable to save chat history', error);
    }
  }, [state]);

  const setHistory = useCallback((update: SetStateAction<ChatMessage[]>) => {
    if (!key) return;
    setState((previous) => {
      // Ignore a response that arrives after its owner has changed.
      if (previous.key !== key) return previous;
      return {
        key,
        history: typeof update === 'function' ? update(previous.history) : update,
      };
    });
  }, [key]);
  const clearHistory = useCallback(() => setHistory([]), [setHistory]);

  return { history: state.history, setHistory, clearHistory };
}
