import apiClient from './client';
import type { APIResponse, HealthData } from '@/types/api';

export async function fetchHealth(): Promise<HealthData> {
  const { data } = await apiClient.get<APIResponse<HealthData>>('/health');
  return data.data;
}
