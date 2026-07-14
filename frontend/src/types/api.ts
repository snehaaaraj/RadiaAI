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
