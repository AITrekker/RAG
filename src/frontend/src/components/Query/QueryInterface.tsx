import React, { useState, useRef } from 'react';
import { useTenant } from '../../contexts/TenantContext';
import apiClient from '../../services/api';
import type { QueryResponse as ApiQueryResponse } from '../../services/api';

export interface QueryResult {
  id: string;
  answer: string;
  sources: Array<{
    id: string;
    filename: string;
    chunk_text: string;
    page?: number;
    confidence?: number;
  }>;
  query: string;
  timestamp: string;
  processing_time?: number;
}

interface QueryInterfaceProps {
  onQuery?: (query: string) => Promise<QueryResult>;
  isLoading?: boolean;
}

export const QueryInterface: React.FC<QueryInterfaceProps> = ({ 
  onQuery, 
  isLoading = false 
}) => {
  const { tenant } = useTenant();
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const primaryColor = tenant?.primaryColor || '#3B82F6';
  const secondaryColor = tenant?.secondaryColor || '#1E40AF';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!query.trim() || isProcessing) return;
    
    setIsProcessing(true);
    setError(null);
    setResult(null);

    try {
      if (onQuery) {
        const queryResult = await onQuery(query.trim());
        setResult(queryResult);
      } else {
        // Use real API
        const apiResponse = await apiClient.processQuery({
          query: query.trim(),
          max_sources: 5,
          include_metadata: true,
          rerank: true
        });
        
        // Convert API response to component format
        const result: QueryResult = {
          id: apiResponse.query_id,
          answer: apiResponse.answer,
          sources: apiResponse.sources.map(source => ({
            id: source.document_id,
            filename: source.filename,
            chunk_text: source.chunk_text,
            page: source.page_number,
            confidence: source.confidence_score
          })),
          query: apiResponse.query,
          timestamp: apiResponse.timestamp,
          processing_time: apiResponse.processing_time
        };
        
        setResult(result);
      }
    } catch (err: any) {
      setError(err.error || err.message || 'An error occurred while processing your query');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  const handleClear = () => {
    setQuery('');
    setResult(null);
    setError(null);
    textareaRef.current?.focus();
  };

  return (
    <div className="max-w-4xl mx-auto">
      {/* Query Input Section */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="query" className="block text-sm font-medium text-gray-700 mb-2">
              Ask a question about your documents
            </label>
            <div className="relative">
              <textarea
                ref={textareaRef}
                id="query"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="e.g., What is the company vacation policy? How do I submit an expense report?"
                                 className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                rows={3}
                disabled={isProcessing}
              />
              {query && (
                <button
                  type="button"
                  onClick={handleClear}
                  className="absolute top-3 right-12 text-gray-400 hover:text-gray-600"
                  disabled={isProcessing}
                >
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          </div>
          
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-500">
              Press Enter to search, Shift+Enter for new line
            </div>
            <button
              type="submit"
              disabled={!query.trim() || isProcessing}
                             className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
               style={{
                 backgroundColor: query.trim() && !isProcessing ? primaryColor : undefined
               }}
            >
              {isProcessing ? (
                <div className="flex items-center space-x-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  <span>Searching...</span>
                </div>
              ) : (
                <div className="flex items-center space-x-2">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <span>Search</span>
                </div>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Loading State */}
      {isProcessing && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
          <div className="flex items-center justify-center space-x-3">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
            <span className="text-gray-600">Processing your query...</span>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <div className="flex items-start space-x-3">
            <svg className="h-5 w-5 text-red-400 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <h3 className="text-sm font-medium text-red-800">Error</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Results Display */}
      {result && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold text-gray-900">Answer</h3>
              {result.processing_time && (
                <span className="text-sm text-gray-500">
                  {result.processing_time.toFixed(1)}s
                </span>
              )}
            </div>
            <div className="prose max-w-none">
              <p className="text-gray-800 leading-relaxed whitespace-pre-wrap">
                {result.answer}
              </p>
            </div>
          </div>

          {/* Sources */}
          {result.sources && result.sources.length > 0 && (
            <div className="border-t border-gray-200 pt-4">
              <h4 className="text-sm font-medium text-gray-900 mb-3">
                Sources ({result.sources.length})
              </h4>
              <div className="space-y-3">
                {result.sources.map((source) => (
                  <div 
                    key={source.id}
                    className="bg-gray-50 rounded-lg p-4 border border-gray-200"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center space-x-2">
                        <svg className="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <span className="text-sm font-medium text-gray-900">
                          {source.filename}
                        </span>
                        {source.page && (
                          <span className="text-sm text-gray-500">
                            Page {source.page}
                          </span>
                        )}
                      </div>
                      {source.confidence && (
                        <span className="text-xs text-gray-500">
                          {Math.round(source.confidence * 100)}% match
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-700 italic">
                      "{source.chunk_text}"
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}; 