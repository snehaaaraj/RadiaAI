import { useQuery } from '@tanstack/react-query';
import { getIngestionJob } from '@/api/ingest';

export function useIngestionJobStatus(jobId: string | null) {
  return useQuery({
    queryKey: ['ingestion-job', jobId],
    queryFn: () => {
      if (!jobId) throw new Error('An ingestion job ID is required.');
      return getIngestionJob(jobId);
    },
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'completed' || status === 'failed' ? false : 2_000;
    },
    staleTime: 1_000,
  });
}
