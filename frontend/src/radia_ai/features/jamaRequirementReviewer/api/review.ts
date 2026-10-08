import apiClient from '@/api/client';
import type {
  APIResponse,
  ApplyFindingDispositionRequest,
  DeltaReviewInput,
  DeltaReviewResponse,
  RequirementReviewInput,
  RequirementReviewResponse,
  ReviewHistoryEntry,
  ReviewHistoryListResponse,
  ReviewWorkflow,
  StandardsResponse,
} from '@/types/api';

/** A review now also synthesizes the final recommendation, so it can take longer than the default. */
const REQUIREMENT_REVIEW_TIMEOUT_MS = 300_000;

export async function reviewRequirement(
  payload: RequirementReviewInput
): Promise<RequirementReviewResponse> {
  const { data } = await apiClient.post<APIResponse<RequirementReviewResponse>>(
    '/review/requirement',
    payload,
    { timeout: REQUIREMENT_REVIEW_TIMEOUT_MS }
  );
  return data.data;
}

export async function reviewDelta(payload: DeltaReviewInput): Promise<DeltaReviewResponse> {
  const { data } = await apiClient.post<APIResponse<DeltaReviewResponse>>('/review/delta', payload);
  return data.data;
}

export async function fetchStandards(): Promise<StandardsResponse> {
  const { data } = await apiClient.get<APIResponse<StandardsResponse>>('/standards');
  return data.data;
}

export async function fetchReviewHistory(
  workflow?: ReviewWorkflow,
  limit = 100
): Promise<ReviewHistoryListResponse> {
  const { data } = await apiClient.get<APIResponse<ReviewHistoryListResponse>>('/review/history', {
    params: { workflow, limit },
  });
  return data.data;
}

export async function applyFindingDisposition(
  reviewId: string,
  payload: ApplyFindingDispositionRequest
): Promise<ReviewHistoryEntry> {
  const { data } = await apiClient.post<APIResponse<ReviewHistoryEntry>>(
    `/review/history/${reviewId}/disposition`,
    payload
  );
  return data.data;
}
