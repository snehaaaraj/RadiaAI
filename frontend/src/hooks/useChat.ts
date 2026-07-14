import { useMutation } from '@tanstack/react-query';
import { sendChatMessage } from '@/api/chat';
import type { ChatData, ChatRequest } from '@/types/api';

/** Sends a chat message to the RAG pipeline. */
export function useChat() {
  return useMutation<ChatData, Error, ChatRequest>({
    mutationFn: sendChatMessage,
  });
}
