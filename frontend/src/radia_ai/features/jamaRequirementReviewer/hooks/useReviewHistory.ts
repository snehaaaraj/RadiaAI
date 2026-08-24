import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { applyFindingDisposition, fetchReviewHistory } from '@/radia_ai/features/jamaRequirementReviewer/api/review';
import type { ApplyFindingDispositionRequest, ReviewWorkflow } from '@/types/api';

export const REVIEW_HISTORY_QUERY_KEY = (workflow?: ReviewWorkflow, limit = 100) =>
  ['review-history', workflow ?? 'all', limit] as const;

export function useReviewHistory(workflow?: ReviewWorkflow, limit = 100) {
  return useQuery({
    queryKey: REVIEW_HISTORY_QUERY_KEY(workflow, limit),
    queryFn: () => fetchReviewHistory(workflow, limit),
    staleTime: 15_000,
  });
}

interface ApplyFindingDispositionVariables {
  reviewId: string;
  payload: ApplyFindingDispositionRequest;
}

export function useApplyFindingDisposition() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ reviewId, payload }: ApplyFindingDispositionVariables) =>
      applyFindingDisposition(reviewId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['review-history'] });
    },
  });
}
