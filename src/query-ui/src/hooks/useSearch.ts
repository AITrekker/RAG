import { useQuery } from '@tanstack/react-query';
import { performSearch, SearchParams, SearchResponse } from '../api/search';

export function useSearch(params: SearchParams) {
  return useQuery<SearchResponse>({
    queryKey: ['search', params],
    queryFn: () => performSearch(params),
    enabled: Boolean(params.query),
    staleTime: 1000 * 60 * 5, // 5 minutes
    gcTime: 1000 * 60 * 30, // 30 minutes
    retry: 1,
  });
} 