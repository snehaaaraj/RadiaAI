import apiClient from './client';
import type {
  APIResponse,
  IngestionJobResponse,
  IngestionStatusResponse,
  IngestRequest,
  IngestResponse,
} from '@/types/api';

export async function triggerIngestion(body: IngestRequest): Promise<IngestResponse> {
  const { data } = await apiClient.post<APIResponse<IngestResponse>>('/ingest', body);
  return data.data;
}

export async function getIngestionStatus(): Promise<IngestionStatusResponse> {
  const { data } = await apiClient.get<APIResponse<IngestionStatusResponse>>('/ingest/status');
  return data.data;
}

export async function getIngestionJob(jobId: string): Promise<IngestionJobResponse> {
  const { data } = await apiClient.get<APIResponse<IngestionJobResponse>>(`/ingest/jobs/${jobId}`);
  return data.data;
}
