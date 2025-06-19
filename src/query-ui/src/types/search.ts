export interface SearchSuggestion {
  id?: string;
  text: string;
  category?: string;
  metadata?: {
    source?: string;
    type?: string;
    [key: string]: any;
  };
}

export interface SearchResult {
  id: string;
  title: string;
  content: string;
  highlightedText: string;
  source: string;
  relevanceScore: number;
  metadata: {
    source: string;
    path?: string;
    lineNumbers?: string;
    timestamp: string;
    type?: string;
    [key: string]: any;
  };
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  processingTime: number;
} 