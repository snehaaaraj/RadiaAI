import { useQuery } from '@tanstack/react-query';
import { getIngestionStatus } from '@/api/ingest';

export const INGESTION_STATUS_QUERY_KEY = ['ingestion-status'] as const;

/**
 * Polls the last-ingestion-run status every 30 seconds so the UI reflects
 * documents that were automatically re-ingested via the SharePoint webhook,
 * not just runs triggered by the manual "Ingest Documents" button.
 */
export function useIngestionStatus() {
  return useQuery({
    queryKey: INGESTION_STATUS_QUERY_KEY,
    queryFn: getIngestionStatus,
    refetchInterval: 30_000,
    staleTime: 20_000,
  });
}
