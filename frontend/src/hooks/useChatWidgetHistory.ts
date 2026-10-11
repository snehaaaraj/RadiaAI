import { useChatHistory } from '@/hooks/useChatHistory';

/** Manages chat widget history, backed by localStorage. */
export function useChatWidgetHistory() {
  return useChatHistory('widget');
}
