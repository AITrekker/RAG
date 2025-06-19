import { SearchResult } from '../types/search';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  page: number;
  pageSize: number;
  query: string;
  processingTime: number;
}

export interface SearchParams {
  query: string;
  page?: number;
  pageSize?: number;
  filters?: Record<string, any>;
}

export async function performSearch(params: SearchParams): Promise<SearchResponse> {
  const searchParams = new URLSearchParams({
    q: params.query,
    page: String(params.page || 1),
    pageSize: String(params.pageSize || 10),
    ...params.filters,
  });

  const response = await fetch(`${API_BASE_URL}/api/search?${searchParams}`);
  if (!response.ok) {
    throw new Error('Search request failed');
  }

  return response.json();
} 