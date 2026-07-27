import { useMutation } from '@tanstack/react-query';
import { reviewDelta } from '@/api/review';
import type { DeltaReviewInput, DeltaReviewResponse } from '@/types/api';

export function useDeltaReview() {
  return useMutation<DeltaReviewResponse, Error, DeltaReviewInput>({
    mutationFn: reviewDelta,
  });
}

