import { useQuery } from '@tanstack/react-query';
import { fetchDocuments } from '@/api/documents';

export const DOCUMENTS_QUERY_KEY = (page: number, pageSize: number) =>
  ['documents', page, pageSize] as const;

export function useDocuments(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: DOCUMENTS_QUERY_KEY(page, pageSize),
    queryFn: () => fetchDocuments(page, pageSize),
    staleTime: 60_000,
  });
}
