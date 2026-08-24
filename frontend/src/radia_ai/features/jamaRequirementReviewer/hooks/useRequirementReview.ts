import { useMutation } from '@tanstack/react-query';
import { reviewRequirement } from '@/radia_ai/features/jamaRequirementReviewer/api/review';
import type { RequirementReviewInput, RequirementReviewResponse } from '@/types/api';

export function useRequirementReview() {
  return useMutation<RequirementReviewResponse, Error, RequirementReviewInput>({
    mutationFn: reviewRequirement,
  });
}
