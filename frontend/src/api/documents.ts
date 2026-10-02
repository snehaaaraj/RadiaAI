import apiClient from './client';
import type {
  APIResponse,
  DocumentDeleteResponse,
  DocumentDetail,
  DocumentSummary,
  PaginatedResponse,
} from '@/types/api';

export interface DocumentListParams {
  page?: number;
  pageSize?: number;
  source?: string;
  query?: string;
  sortBy?: 'filename' | 'source' | 'chunk_count' | 'ingested_at';
  sortOrder?: 'asc' | 'desc';
}

export async function fetchDocuments({
  page = 1,
  pageSize = 20,
  source,
  query,
  sortBy = 'filename',
  sortOrder = 'asc',
}: DocumentListParams = {}): Promise<PaginatedResponse<DocumentSummary>> {
  const { data } = await apiClient.get<PaginatedResponse<DocumentSummary>>('/documents', {
    params: {
      page,
      page_size: pageSize,
      source: source || undefined,
      query: query || undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
    },
  });
  return data;
}

export async function fetchDocument(documentId: string): Promise<DocumentDetail> {
  const { data } = await apiClient.get<APIResponse<DocumentDetail>>(
    `/documents/${encodeURIComponent(documentId)}`
  );
  return data.data;
}

export async function deleteDocument(documentId: string): Promise<DocumentDeleteResponse> {
  const { data } = await apiClient.delete<DocumentDeleteResponse>(
    `/documents/${encodeURIComponent(documentId)}`
  );
  return data;
}
