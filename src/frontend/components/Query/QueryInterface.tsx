import React, { useState, useRef } from 'react';
import { useTenant } from '../../contexts/TenantContext';
import { OpenAPI, QueryService, QueryResponse, ApiError, Source } from '../../services/api.generated.ts';

export type QueryResult = QueryResponse & {
  id: string;
  timestamp: string;
};

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

  React.useEffect(() => {
    if (tenant?.id) {
      OpenAPI.HEADERS = {
        ...OpenAPI.HEADERS,
        'X-Tenant-ID': tenant.id,
      };
      console.log(`QueryInterface: Set tenant to ${tenant.id} (${tenant.name})`);
    }
  }, [tenant]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!query.trim() || isProcessing) return;
    
    if (query.trim().length < 3) {
      setError('Query must be at least 3 characters long');
      return;
    }
    
    setIsProcessing(true);
    setError(null);
    setResult(null);

    try {
      if (onQuery) {
        const queryResult = await onQuery(query.trim());
        setResult(queryResult);
      } else {
        const apiResponse = await QueryService.postApiV1Query({
          requestBody: {
            query: query.trim(),
            max_sources: 5,
            include_metadata: true,
            rerank: true
          }
        });
        
        const resultData: QueryResult = {
          ...apiResponse,
          id: apiResponse.query_id || `query_${Date.now()}`,
          timestamp: new Date().toISOString(),
        };
        
        setResult(resultData);
      }
    } catch (err: any) {
      console.error('Query error:', err);
      if (err instanceof ApiError) {
        const errorBody = err.body as { detail?: string | { msg: string }[] };
        if (err.status === 422 && errorBody.detail) {
          if (typeof errorBody.detail === 'string') {
            setError(errorBody.detail);
          } else if (Array.isArray(errorBody.detail)) {
            setError(errorBody.detail.map(d => d.msg).join(', '));
          } else {
            setError('A validation error occurred.');
          }
        } else {
          setError(typeof errorBody.detail === 'string' ? errorBody.detail : err.message);
        }
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred while processing your query');
      }
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
              {query.trim() && query.trim().length < 3 && (
                <span className="text-red-500 ml-2">
                  (Minimum 3 characters required)
                </span>
              )}
            </div>
            <button
              type="submit"
              disabled={!query.trim() || query.trim().length < 3 || isProcessing}
                             className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
               style={{
                 backgroundColor: query.trim() && query.trim().length >= 3 && !isProcessing ? primaryColor : undefined
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
                {result.sources.map((source: Source) => (
                  <div
                    key={source.document_id}
                    className="bg-gray-50 rounded-md p-3 border border-gray-200"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <h5 className="font-semibold text-gray-800 truncate" title={source.filename}>
                        {source.filename}
                      </h5>
                      <div className="flex items-center space-x-3 text-xs text-gray-500">
                        {source.page_number && (
                          <span className="bg-gray-200 rounded-full px-2 py-0.5">
                            Page {source.page_number}
                          </span>
                        )}
                        {source.confidence_score && (
                           <span className="font-medium">
                             {(source.confidence_score * 100).toFixed(0)}%
                           </span>
                        )}
                      </div>
                    </div>
                    <p className="text-sm text-gray-600 line-clamp-3">
                      {source.chunk_text}
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