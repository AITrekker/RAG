import { useQuery } from '@tanstack/react-query';
import { fetchSuggestions } from '../api/suggestions';
import { SearchSuggestion } from '../types/search';

export function useSearchSuggestions(query: string) {
  return useQuery<SearchSuggestion[]>({
    queryKey: ['suggestions', query],
    queryFn: () => fetchSuggestions(query),
    enabled: query.length >= 2,
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes
    gcTime: 1000 * 60 * 30, // Keep in cache for 30 minutes
    refetchOnWindowFocus: false,
  });
} 