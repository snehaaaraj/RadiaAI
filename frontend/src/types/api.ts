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
  /**
   * 'inline' (default) cites source filenames in parentheses within the answer
   * text; 'none' omits filenames from the answer text entirely. The
   * structured `citations` array on the response is always returned either way.
   */
  citation_style?: 'inline' | 'none';
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

export interface DocumentChunk {
  chunk_id: string;
  content: string;
  chunk_index: number;
  page_number: number | null;
  section: string;
}

export interface DocumentDetail extends DocumentSummary {
  chunks: DocumentChunk[];
}

export interface DocumentDeleteResponse {
  document_id: string;
  message: string;
}

export interface IngestRequest {
  source: 'blob' | 'sharepoint';
  document_ids?: string[];
}

export interface IngestResponse {
  job_id: string;
  queued_count: number;
  message: string;
}

export interface IngestionStatusResponse {
  timestamp: string | null;
  source: string | null;
  trigger: 'manual' | 'webhook' | null;
  outcome: 'success' | 'error' | null;
  processed: number;
  skipped: number;
  failed: number;
  message: string;
}

export interface IngestionJobResponse {
  job_id: string;
  source: string;
  trigger: 'manual' | 'webhook';
  status: 'queued' | 'processing' | 'retrying' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  attempt: number;
  processed: number;
  skipped: number;
  failed: number;
  message: string;
  failure_details: Array<Record<string, string>>;
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
 * with status 'failed' means it was never evaluated - the UI must never present
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
  /**
   * Finding-derived quality score for the category, 0-10. A category with no
   * findings scores a full 10. Older payloads may omit it, in which case the
   * status is used as a fallback.
   */
  score?: number;
}

export type SourceType = 'skillz_rule' | 'standard';

export interface ReviewFinding {
  /** Stable ID within its review (F1, F2, ...). Absent on reviews stored before synthesis. */
  finding_id?: string | null;
  source_type?: SourceType;
  /** Application-defined authority level of the source; 1 is the highest. */
  authority_level?: number;
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
  source_page: number | null;
  source_section: string | null;
  source_excerpt: string | null;
  source_chunk_id: string | null;
}

export interface RequirementReviewInput {
  requirement_id?: string | null;
  text: string;
  requirement_level?: string | null;
  metadata?: Record<string, string>;
}

export interface DeltaReviewInput {
  specification_id?: string | null;
  baseline_requirements: RequirementReviewInput[];
  updated_requirements: RequirementReviewInput[];
}

export type ContributionStatus =
  | 'applied'
  | 'merged_duplicate'
  | 'overridden'
  | 'conflict_unresolved'
  | 'rejected_unsupported'
  | 'out_of_scope'
  | 'not_addressed';

export type ConflictResolution = 'resolved_by_skillz' | 'unresolved';
export type SkillzStatus = 'applied' | 'not_applicable' | 'unavailable';
export type RecommendationStatus = 'ready' | 'needs_review' | 'no_change' | 'failed';

export interface SkillzRuleReference {
  rule_id: string;
  title: string;
  document: string;
  text: string;
  source_url: string | null;
  source_type: SourceType;
  authority_level: number;
}

export interface FindingContribution {
  finding_id: string;
  status: ContributionStatus;
  contribution: string;
  reason: string;
  overridden_by_rule_ids: string[];
  duplicate_of: string | null;
  conflict_id: string | null;
}

export interface SkillzChange {
  rule_id: string;
  change: string;
  reason: string;
}

export interface RecommendationConflict {
  conflict_id: string;
  finding_ids: string[];
  description: string;
  resolution: ConflictResolution;
  governing_rule_ids: string[];
}

export interface RecommendationOpenItem {
  rule_id: string | null;
  description: string;
}

export interface SkillzCheckIssue {
  rule_id: string;
  term: string;
  message: string;
}

/** One synthesized replacement Description with full provenance to the findings. */
export interface FinalRecommendation {
  status: RecommendationStatus;
  original_description: string;
  recommended_description: string | null;
  summary: string;
  skillz_status: SkillzStatus;
  skillz_status_message: string;
  skillz_package: string | null;
  skillz_revision: string | null;
  skillz_content_hash: string | null;
  skillz_source_url: string | null;
  contributions: FindingContribution[];
  skillz_changes: SkillzChange[];
  conflicts: RecommendationConflict[];
  open_items: RecommendationOpenItem[];
  skillz_rules: SkillzRuleReference[];
  skillz_check_issues: SkillzCheckIssue[];
  failure_message: string;
  prompt_version: string;
}

export interface RequirementReviewResponse {
  review_id: string | null;
  overall: ReviewStatus;
  completion: ReviewCompletion;
  category_results: CategoryResult[];
  findings: ReviewFinding[];
  determinism: DeterminismContext;
  /** Normalized requirement text that was reviewed. */
  requirement_text?: string | null;
  /** Null when the review did not complete; absent on results stored before synthesis. */
  final_recommendation?: FinalRecommendation | null;
}

export interface DeltaChangeSummary {
  new_requirement_ids: string[];
  modified_requirement_ids: string[];
  deleted_requirement_ids: string[];
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
  finding_to_requirement_map: Record<number, string>; // For delta: flattened index -> requirement_id
  requirement_text?: string | null;
  final_recommendation?: FinalRecommendation | null;
}

export interface ReviewHistoryListResponse {
  total: number;
  entries: ReviewHistoryEntry[];
}

// ---------------------------------------------------------------------------
// Jama Connect integration
// ---------------------------------------------------------------------------

export interface JamaProject {
  id: number;
  name: string;
  project_key: string | null;
  is_folder: boolean;
}

export interface JamaProjectList {
  projects: JamaProject[];
}

export interface JamaRequirementSummary {
  id: number;
  document_key: string | null;
  global_id: string | null;
  name: string;
  item_type_id: number | null;
  project_id: number | null;
}

export interface JamaRequirementSearchResult {
  results: JamaRequirementSummary[];
  total: number;
  start_at: number;
  max_results: number;
}

export interface JamaRequirement {
  id: number;
  document_key: string | null;
  global_id: string | null;
  name: string;
  description: string;
  rationale: string;
  status: string | null;
  item_type_id: number | null;
  project_id: number | null;
  created_date: string | null;
  modified_date: string | null;
  web_url: string | null;
  fields: Record<string, unknown>;
}
