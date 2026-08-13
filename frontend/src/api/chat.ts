import apiClient from './client';
import type { APIResponse, ChatData, ChatRequest } from '@/types/api';

export async function sendChatMessage(request: ChatRequest): Promise<ChatData> {
  const { data } = await apiClient.post<APIResponse<ChatData>>('/chat', request);
  return data.data;
}
