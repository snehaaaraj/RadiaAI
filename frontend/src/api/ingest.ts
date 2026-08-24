import apiClient from './client';
import type { APIResponse, IngestRequest, IngestResponse } from '@/types/api';

export async function triggerIngestion(body: IngestRequest): Promise<IngestResponse> {
  const { data } = await apiClient.post<APIResponse<IngestResponse>>('/ingest', body);
  return data.data;
}
