import apiClient from '@/api/client';
import type {
  APIResponse,
  JamaProjectList,
  JamaRequirement,
  JamaRequirementSearchResult,
} from '@/types/api';

export async function fetchJamaProjects(): Promise<JamaProjectList> {
  const { data } = await apiClient.get<APIResponse<JamaProjectList>>('/jama/projects');
  return data.data;
}

export interface JamaRequirementSearchParams {
  projectId?: number;
  contains?: string;
  itemTypeId?: number;
  startAt?: number;
  maxResults?: number;
}

export async function searchJamaRequirements(
  params: JamaRequirementSearchParams
): Promise<JamaRequirementSearchResult> {
  const { data } = await apiClient.get<APIResponse<JamaRequirementSearchResult>>(
    '/jama/requirements',
    {
      params: {
        project_id: params.projectId,
        contains: params.contains,
        item_type_id: params.itemTypeId,
        start_at: params.startAt,
        max_results: params.maxResults,
      },
    }
  );
  return data.data;
}

export async function fetchJamaRequirement(itemId: number): Promise<JamaRequirement> {
  const { data } = await apiClient.get<APIResponse<JamaRequirement>>(
    `/jama/requirements/${itemId}`
  );
  return data.data;
}
