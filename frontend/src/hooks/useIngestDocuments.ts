import { useMutation } from '@tanstack/react-query';
import { triggerIngestion } from '@/api/ingest';
import type { IngestRequest } from '@/types/api';

export function useIngestDocuments() {
  return useMutation({
    mutationFn: (body: IngestRequest) => triggerIngestion(body),
  });
}
