import { useQuery } from '@tanstack/react-query';
import { fetchHealth } from '@/api/health';

export const HEALTH_QUERY_KEY = ['health'] as const;

/** Polls the backend health endpoint every 30 seconds. */
export function useHealth() {
  return useQuery({
    queryKey: HEALTH_QUERY_KEY,
    queryFn: fetchHealth,
    refetchInterval: 30_000,
    staleTime: 20_000,
  });
}
