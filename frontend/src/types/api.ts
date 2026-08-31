/**
 * Shared TypeScript types that mirror the backend API schemas.
 * Keep these in sync with backend/app/schemas/ as the API evolves.
 */

// ---------------------------------------------------------------------------
// Common response envelopes
// ---------------------------------------------------------------------------

export interface APIResponse<T> {
  success: boolean;
  data: T;
  request_id: string;
}

export interface ErrorDetail {
  code: string;
  message: string;
  detail: Record<string, unknown>;
}

export interface ErrorResponse {
  success: false;
  error: ErrorDetail;
  request_id: string;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  total: number;
  page: number;
  page_size: number;
  request_id: string;
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export type ServiceStatus = 'ok' | 'degraded' | 'down';

export interface DependencyHealth {
  name: string;
  status: ServiceStatus;
  latency_ms: number | null;
  message: string;
}

export interface HealthData {
  status: ServiceStatus;
  version: string;
  environment: string;
  dependencies: DependencyHealth[];
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  question: string;
  conversation_history?: ChatMessage[];
  top_k?: number;
}

export interface CitedChunk {
  chunk_id: string;
  source: string;
  filename: string;
  section: string;
  page_number: number | null;
  score: number;
  content_snippet: string;
}

export interface ChatData {
  answer: string;
  citations: CitedChunk[];
  model: string;
  retrieval_count: number;
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export type SearchMode = 'keyword' | 'vector' | 'hybrid';

export interface SearchRequest {
  query: string;
  mode?: SearchMode;
  top_k?: number;
  filters?: Record<string, unknown>;
}

export interface SearchResult {
  chunk_id: string;
  score: number;
  source: string;
  filename: string;
  document_type: string;
  section: string;
  page_number: number | null;
  content: string;
  highlights: string[];
}

export interface SearchData {
  results: SearchResult[];
  total: number;
  mode: SearchMode;
}

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

export type DocumentStatus = 'pending' | 'processing' | 'indexed' | 'failed';

export interface DocumentMetadata {
  source: string;
  filename: string;
  document_type: string;
  author: string;
  version: string;
  modified_date: string | null;
}

export interface DocumentSummary {
  document_id: string;
  filename: string;
  status: DocumentStatus;
  chunk_count: number;
  metadata: DocumentMetadata;
  ingested_at: string | null;
}

export interface IngestRequest {
  source: string;
  document_ids?: string[];
}

export interface IngestResponse {
  job_id: string;
  queued_count: number;
  message: string;
}

// ---------------------------------------------------------------------------
// Requirements review
// ---------------------------------------------------------------------------

export type ReviewStatus =
  | 'Acceptable'
  | 'Revision Recommended'
  | 'Unacceptable'
  | 'Not Evaluated';
export type PassFail = 'Pass' | 'Fail';
export type FindingSeverity = 'Low' | 'Medium' | 'High' | 'Critical';
export type ReviewWorkflow = 'requirement' | 'delta';
export type FindingDispositionStatus = 'Accepted' | 'Rejected' | 'Deferred';
export type TraceLinkChangeType = 'added' | 'removed' | 'modified';

export type ReviewCompletionStatus = 'complete' | 'partial' | 'failed';

export type ReviewFailureReason =
  | 'review_engine_unavailable'
  | 'no_standards_context'
  | 'retrieval_failed'
  | 'llm_call_failed'
  | 'invalid_llm_response';

/**
 * Outcome of the review *process*, separate from the review *verdict*.
 *
 * Zero findings with status 'complete' means the requirement passed. Zero findings
 * with status 'failed' means it was never evaluated — the UI must never present
 * those two the same way.
 */
export interface ReviewCompletion {
  status: ReviewCompletionStatus;
  reason: ReviewFailureReason | null;
  message: string;
}

export interface DeterminismConfigSnapshot {
  temperature: number;
  max_tokens: number;
  retrieval_top_k: number;
}

export interface DeterminismContext {
  reviewer_bundle_version: string;
  prompt_versions: Record<string, string>;
  standards_versions: Record<string, string>;
  config_hash: string;
  config_snapshot: DeterminismConfigSnapshot;
}

export interface CategoryResult {
  category: string;
  status: ReviewStatus;
}

export interface ReviewFinding {
  category: string;
  reviewer: string;
  severity: FindingSeverity;
  pass_fail: PassFail;
  status: ReviewStatus;
  rule: string;
  explanation: string;
  evidence: string;
  recommendation: string;
  reference: string;
  reference_title: string | null;
  reference_url: string | null;
  suggested_rewrite: string | null;
}

export interface RequirementReviewInput {
  requirement_id?: string | null;
  text: string;
  requirement_level?: string | null;
  metadata?: Record<string, string>;
}

export interface TraceLinkChange {
  requirement_id: string;
  change_type: TraceLinkChangeType;
  previous_parent_id?: string | null;
  current_parent_id?: string | null;
}

export interface DeltaReviewInput {
  specification_id?: string | null;
  baseline_requirements: RequirementReviewInput[];
  updated_requirements: RequirementReviewInput[];
  changed_trace_links?: TraceLinkChange[];
}

export interface RequirementReviewResponse {
  review_id: string | null;
  overall: ReviewStatus;
  completion: ReviewCompletion;
  category_results: CategoryResult[];
  findings: ReviewFinding[];
  determinism: DeterminismContext;
}

export interface DeltaChangeSummary {
  new_requirement_ids: string[];
  modified_requirement_ids: string[];
  deleted_requirement_ids: string[];
  changed_trace_link_requirement_ids: string[];
}

export interface DeltaRequirementReviewResult {
  requirement_id: string;
  overall: ReviewStatus;
  completion: ReviewCompletion;
  category_results: CategoryResult[];
  findings: ReviewFinding[];
}

export interface DeltaReviewResponse {
  review_id: string | null;
  overall: ReviewStatus;
  completion: ReviewCompletion;
  change_summary: DeltaChangeSummary;
  reviewed_requirements: DeltaRequirementReviewResult[];
  determinism: DeterminismContext;
}

export interface StandardReference {
  key: string;
  name: string;
  version: string;
  source: string;
  categories: string[];
  description: string;
  sharepoint_url: string | null;
  file_type: string | null;
  last_modified: string | null;
  file_size_bytes: number | null;
}

export interface StandardsResponse {
  standards: StandardReference[];
  source: 'sharepoint' | 'registry' | 'fallback';
}

export interface FindingDisposition {
  finding_index: number;
  disposition: FindingDispositionStatus;
  reviewer_comment: string;
  reviewer_id: string | null;
  updated_at: string;
}

export interface ApplyFindingDispositionRequest {
  finding_index: number;
  disposition: FindingDispositionStatus;
  reviewer_comment?: string;
  reviewer_id?: string | null;
}

export interface ReviewHistoryEntry {
  review_id: string;
  workflow: ReviewWorkflow;
  subject_id: string | null;
  created_at: string;
  overall: ReviewStatus;
  completion: ReviewCompletion;
  category_results: CategoryResult[];
  findings: ReviewFinding[];
  determinism: DeterminismContext;
  dispositions: FindingDisposition[];
}

export interface ReviewHistoryListResponse {
  total: number;
  entries: ReviewHistoryEntry[];
}
