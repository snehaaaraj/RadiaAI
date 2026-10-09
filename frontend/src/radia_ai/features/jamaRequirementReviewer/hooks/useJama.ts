import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchJamaAccount,
  fetchJamaProjects,
  fetchJamaRequirement,
  linkJamaAccount,
  searchJamaRequirements,
  unlinkJamaAccount,
} from '@/radia_ai/features/jamaRequirementReviewer/api/jama';
import type { ErrorResponse } from '@/types/api';

export const JAMA_PROJECTS_QUERY_KEY = ['jama', 'projects'] as const;
export const JAMA_ACCOUNT_QUERY_KEY = ['jama', 'account'] as const;

/** Error codes meaning the user must (re)link their own Jama account in Settings. */
export const JAMA_LINK_REQUIRED_CODES = new Set([
  'JAMA_ACCOUNT_NOT_LINKED',
  'JAMA_CREDENTIALS_INVALID',
]);

export function jamaErrorCode(error: unknown): string | undefined {
  return (error as ErrorResponse | undefined)?.error?.code;
}

export function useJamaAccount() {
  return useQuery({
    queryKey: JAMA_ACCOUNT_QUERY_KEY,
    queryFn: fetchJamaAccount,
    staleTime: 60_000,
    retry: false,
  });
}

/** Link or unlink the user's Jama account, then refetch everything Jama-scoped. */
export function useJamaAccountMutations() {
  const queryClient = useQueryClient();
  const onSuccess = () => queryClient.invalidateQueries({ queryKey: ['jama'] });
  const link = useMutation({ mutationFn: linkJamaAccount, onSuccess });
  const unlink = useMutation({ mutationFn: unlinkJamaAccount, onSuccess });
  return { link, unlink };
}

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
