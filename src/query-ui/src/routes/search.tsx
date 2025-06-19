import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Container, Typography, useTheme, useMediaQuery } from '@mui/material';
import { SearchInput } from '../components/SearchInput';
import { SearchResults } from '../components/SearchResults';
import { useSearchHistory } from '../hooks/useSearchHistory';
import { useSearch } from '../hooks/useSearch';

export function Component() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState(searchParams.get('q') || '');
  const [page, setPage] = useState(Number(searchParams.get('page')) || 1);
  const { addToHistory } = useSearchHistory();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const { data, isLoading, error } = useSearch({
    query: searchQuery,
    page,
    pageSize: 10,
  });

  useEffect(() => {
    const query = searchParams.get('q');
    const pageParam = searchParams.get('page');
    if (query) {
      setSearchQuery(query);
      addToHistory(query);
    }
    if (pageParam) {
      setPage(Number(pageParam));
    }
  }, [searchParams, addToHistory]);

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setPage(1);
    setSearchParams({ q: query, page: '1' });
    addToHistory(query);
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    setSearchParams({ q: searchQuery, page: String(newPage) });
  };

  return (
    <div className={`py-4 ${isMobile ? 'px-2' : 'py-8'}`}>
      <Typography
        variant={isMobile ? 'h5' : 'h4'}
        component="h1"
        className="text-center mb-4 sm:mb-8"
      >
        Document Search
      </Typography>
      <div className="max-w-3xl mx-auto">
        <SearchInput onSearch={handleSearch} />
        {searchQuery && (
          <div className={isMobile ? 'mt-4' : 'mt-8'}>
            <SearchResults
              results={data?.results || []}
              total={data?.total || 0}
              page={page}
              pageSize={10}
              isLoading={isLoading}
              error={error as Error}
              processingTime={data?.processingTime}
              onPageChange={handlePageChange}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default Component; 