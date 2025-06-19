import { SearchSuggestion } from '../types/search';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export async function fetchSuggestions(query: string): Promise<SearchSuggestion[]> {
  if (!query || query.length < 2) return [];

  try {
    const response = await fetch(`${API_BASE_URL}/api/suggestions?q=${encodeURIComponent(query)}`);
    if (!response.ok) {
      throw new Error('Failed to fetch suggestions');
    }
    return await response.json();
  } catch (error) {
    console.error('Error fetching suggestions:', error);
    return [];
  }
} 