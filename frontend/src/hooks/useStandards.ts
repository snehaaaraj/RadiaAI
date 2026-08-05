import { useQuery } from '@tanstack/react-query';
import { fetchStandards } from '@/api/review';

export const STANDARDS_QUERY_KEY = ['standards'] as const;

export function useStandards() {
  return useQuery({
    queryKey: STANDARDS_QUERY_KEY,
    queryFn: fetchStandards,
    staleTime: 60_000,
  });
}

