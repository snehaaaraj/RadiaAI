import apiClient from './client';
import type { APIResponse, SearchData, SearchRequest } from '@/types/api';

export async function searchDocuments(request: SearchRequest): Promise<SearchData> {
  const { data } = await apiClient.post<APIResponse<SearchData>>('/search', request);
  return data.data;
}
