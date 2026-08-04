import apiClient from './client';
import type { PaginatedResponse, DocumentSummary } from '@/types/api';

export async function fetchDocuments(page = 1, pageSize = 20): Promise<PaginatedResponse<DocumentSummary>> {
  const { data } = await apiClient.get<PaginatedResponse<DocumentSummary>>('/documents', {
    params: { page, page_size: pageSize },
  });
  return data;
}
