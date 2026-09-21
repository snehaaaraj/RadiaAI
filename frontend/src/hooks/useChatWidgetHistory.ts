/**
 * Persists the chat widget's conversation history to localStorage so it
 * survives route changes, page reloads, and closing/reopening the widget.
 *
 * Mirrors the persistence pattern used for UI preferences in AppContext.
 */

import { useEffect, useState } from 'react';

const STORAGE_KEY = 'radia-chat-widget-history';

export interface ChatWidgetTurn {
  role: 'user' | 'assistant';
  content: string;
}

function loadHistory(): ChatWidgetTurn[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as ChatWidgetTurn[]) : [];
  } catch {
    return [];
  }
}

/** Manages chat widget history, backed by localStorage. */
export function useChatWidgetHistory() {
  const [history, setHistory] = useState<ChatWidgetTurn[]>(loadHistory);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  }, [history]);

  const clearHistory = () => setHistory([]);

  return { history, setHistory, clearHistory };
}
