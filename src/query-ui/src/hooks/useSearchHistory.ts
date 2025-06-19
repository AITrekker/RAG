import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

interface SearchHistoryEntry {
  id: string;
  query: string;
  timestamp: string;
  resultCount?: number;
}

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

async function fetchSearchHistory(): Promise<SearchHistoryEntry[]> {
  const response = await fetch(`${API_BASE_URL}/api/search/history`);
  if (!response.ok) {
    throw new Error('Failed to fetch search history');
  }
  return response.json();
}

async function addToHistory(query: string): Promise<SearchHistoryEntry> {
  const response = await fetch(`${API_BASE_URL}/api/search/history`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query }),
  });
  if (!response.ok) {
    throw new Error('Failed to add to search history');
  }
  return response.json();
}

async function clearHistory(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/search/history`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error('Failed to clear search history');
  }
}

export function useSearchHistory() {
  const queryClient = useQueryClient();

  const { data: history = [], isLoading } = useQuery<SearchHistoryEntry[]>({
    queryKey: ['searchHistory'],
    queryFn: fetchSearchHistory,
    staleTime: 1000 * 60, // 1 minute
  });

  const addMutation = useMutation({
    mutationFn: addToHistory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['searchHistory'] });
    },
  });

  const clearMutation = useMutation({
    mutationFn: clearHistory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['searchHistory'] });
    },
  });

  return {
    history,
    isLoading,
    addToHistory: addMutation.mutate,
    clearHistory: clearMutation.mutate,
    isAdding: addMutation.isPending,
    isClearing: clearMutation.isPending,
  };
} 