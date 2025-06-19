import React from 'react';
import {
  Typography,
  Paper,
  Pagination,
  CircularProgress,
  Alert,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import { SearchResult } from '../types/search';
import { SourceCitation } from './SourceCitation';
import { RelevanceIndicator } from './RelevanceIndicator';

interface SearchResultsProps {
  results: SearchResult[];
  total: number;
  page: number;
  pageSize: number;
  isLoading: boolean;
  error: Error | null;
  processingTime?: number;
  onPageChange: (page: number) => void;
}

export function SearchResults({
  results,
  total,
  page,
  pageSize,
  isLoading,
  error,
  processingTime,
  onPageChange,
}: SearchResultsProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <CircularProgress />
      </div>
    );
  }

  if (error) {
    return (
      <Alert severity="error" className="mb-4">
        {error.message}
      </Alert>
    );
  }

  if (results.length === 0) {
    return (
      <Paper className={`p-4 ${isMobile ? 'text-sm' : ''}`}>
        <Typography>No results found. Try a different search term.</Typography>
      </Paper>
    );
  }

  return (
    <div>
      <div className={`flex justify-between items-center mb-2 ${isMobile ? 'text-sm' : ''}`}>
        <Typography variant="body2" color="textSecondary">
          {total.toLocaleString()} results
          {processingTime !== undefined &&
            ` (${processingTime.toFixed(2)} seconds)`}
        </Typography>
        <Typography variant="body2" color="textSecondary">
          Page {page} of {Math.ceil(total / pageSize)}
        </Typography>
      </div>

      <div className={`space-y-${isMobile ? '2' : '4'}`}>
        {results.map((result) => (
          <Paper
            key={result.id}
            className={`p-${isMobile ? '3' : '4'} hover:shadow-md transition-shadow`}
          >
            <div className="flex flex-col space-y-2">
              <div className="flex justify-between items-start">
                <Typography
                  variant={isMobile ? 'body1' : 'h6'}
                  component="h2"
                  className="font-medium flex-grow"
                >
                  {result.title}
                </Typography>
                <RelevanceIndicator
                  score={result.relevanceScore}
                  size={isMobile ? 'small' : 'medium'}
                />
              </div>

              <Typography
                variant="body2"
                className={`text-gray-600 ${isMobile ? 'text-sm' : ''}`}
                dangerouslySetInnerHTML={{ __html: result.highlightedText }}
              />

              <div className={`mt-${isMobile ? '2' : '3'}`}>
                <SourceCitation
                  source={result.source}
                  metadata={result.metadata}
                  size={isMobile ? 'small' : 'medium'}
                />
              </div>
            </div>
          </Paper>
        ))}
      </div>

      {total > pageSize && (
        <div className={`flex justify-center mt-${isMobile ? '4' : '6'}`}>
          <Pagination
            count={Math.ceil(total / pageSize)}
            page={page}
            onChange={(_, value) => onPageChange(value)}
            color="primary"
            size={isMobile ? 'small' : 'medium'}
          />
        </div>
      )}
    </div>
  );
} 