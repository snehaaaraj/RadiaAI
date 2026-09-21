import { useMutation, useQueryClient } from '@tanstack/react-query';
import { triggerIngestion } from '@/api/ingest';
import { INGESTION_STATUS_QUERY_KEY } from '@/hooks/useIngestionStatus';
import type { IngestRequest } from '@/types/api';

export function useIngestDocuments() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: IngestRequest) => triggerIngestion(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: INGESTION_STATUS_QUERY_KEY });
    },
  });
}
