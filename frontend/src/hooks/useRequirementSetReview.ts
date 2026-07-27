import { useMutation } from '@tanstack/react-query';
import { reviewRequirementSet } from '@/api/review';
import type { RequirementSetReviewInput, RequirementSetReviewResponse } from '@/types/api';

export function useRequirementSetReview() {
  return useMutation<RequirementSetReviewResponse, Error, RequirementSetReviewInput>({
    mutationFn: reviewRequirementSet,
  });
}

