import { useQuery } from '@tanstack/react-query';
import {
  fetchJamaProjects,
  fetchJamaRequirement,
  searchJamaRequirements,
} from '@/radia_ai/features/jamaRequirementReviewer/api/jama';

export const JAMA_PROJECTS_QUERY_KEY = ['jama', 'projects'] as const;

export function useJamaProjects() {
  return useQuery({
    queryKey: JAMA_PROJECTS_QUERY_KEY,
    queryFn: fetchJamaProjects,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useJamaRequirementSearch(params: {
  projectId?: number;
  contains?: string;
  enabled?: boolean;
}) {
  const { projectId, contains, enabled = true } = params;
  return useQuery({
    queryKey: ['jama', 'requirements', projectId ?? null, contains ?? ''] as const,
    queryFn: () => searchJamaRequirements({ projectId, contains, maxResults: 50 }),
    enabled,
    staleTime: 30_000,
    retry: false,
  });
}

export function useJamaRequirement(itemId: number | null) {
  return useQuery({
    queryKey: ['jama', 'requirement', itemId] as const,
    queryFn: () => fetchJamaRequirement(itemId as number),
    enabled: itemId != null,
    retry: false,
  });
}
