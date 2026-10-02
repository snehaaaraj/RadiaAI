import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  deleteDocument,
  fetchDocument,
  fetchDocuments,
  type DocumentListParams,
} from '@/api/documents';

export const DOCUMENTS_QUERY_KEY = (params: DocumentListParams = {}) =>
  ['documents', params] as const;

export function useDocuments(params: DocumentListParams = {}) {
  return useQuery({
    queryKey: DOCUMENTS_QUERY_KEY(params),
    queryFn: () => fetchDocuments(params),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
}

export function useDocument(documentId: string | null) {
  return useQuery({
    queryKey: ['documents', 'detail', documentId] as const,
    queryFn: () => fetchDocument(documentId as string),
    enabled: documentId !== null,
    staleTime: 60_000,
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteDocument,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}
