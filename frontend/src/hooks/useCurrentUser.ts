import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/client';
import type { APIResponse, CurrentUser } from '@/types/api';

export const CURRENT_USER_QUERY_KEY = ['auth', 'me'] as const;

export async function fetchCurrentUser(): Promise<CurrentUser> {
  const { data } = await apiClient.get<APIResponse<CurrentUser>>('/auth/me');
  return data.data;
}

/** The signed-in user and their Radia roles, as verified by the API. */
export function useCurrentUser() {
  return useQuery({
    queryKey: CURRENT_USER_QUERY_KEY,
    queryFn: fetchCurrentUser,
    staleTime: 5 * 60_000,
    retry: false,
  });
}
