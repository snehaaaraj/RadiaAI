import { useMutation } from '@tanstack/react-query';
import { reviewDelta } from '@/radia_ai/features/jamaRequirementReviewer/api/review';
import type { DeltaReviewInput, DeltaReviewResponse } from '@/types/api';

export function useDeltaReview() {
  return useMutation<DeltaReviewResponse, Error, DeltaReviewInput>({
    mutationFn: reviewDelta,
  });
}
