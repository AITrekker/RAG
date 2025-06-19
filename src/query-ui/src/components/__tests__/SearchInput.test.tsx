import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@mui/material';
import theme from '../../theme';
import { SearchInput } from '../SearchInput';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

const renderWithProviders = (component: React.ReactNode) => {
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        {component}
      </ThemeProvider>
    </QueryClientProvider>
  );
};

describe('SearchInput', () => {
  beforeEach(() => {
    queryClient.clear();
  });

  it('renders search input with placeholder', () => {
    const onSearch = jest.fn();
    renderWithProviders(<SearchInput onSearch={onSearch} />);
    
    expect(screen.getByPlaceholderText('Search documents...')).toBeInTheDocument();
  });

  it('shows validation error for short queries', async () => {
    const onSearch = jest.fn();
    renderWithProviders(<SearchInput onSearch={onSearch} />);
    
    const input = screen.getByPlaceholderText('Search documents...');
    fireEvent.change(input, { target: { value: 'a' } });
    fireEvent.submit(input);

    await waitFor(() => {
      expect(screen.getByText('Search query must be at least 2 characters')).toBeInTheDocument();
    });
    expect(onSearch).not.toHaveBeenCalled();
  });

  it('calls onSearch with valid query', async () => {
    const onSearch = jest.fn();
    renderWithProviders(<SearchInput onSearch={onSearch} />);
    
    const input = screen.getByPlaceholderText('Search documents...');
    fireEvent.change(input, { target: { value: 'test query' } });
    fireEvent.submit(input);

    await waitFor(() => {
      expect(onSearch).toHaveBeenCalledWith('test query');
    });
  });

  it('shows loading indicator while fetching suggestions', async () => {
    const onSearch = jest.fn();
    renderWithProviders(<SearchInput onSearch={onSearch} />);
    
    const input = screen.getByPlaceholderText('Search documents...');
    fireEvent.change(input, { target: { value: 'test' } });

    await waitFor(() => {
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });
  });

  it('shows suggestions when available', async () => {
    const onSearch = jest.fn();
    renderWithProviders(<SearchInput onSearch={onSearch} />);
    
    const input = screen.getByPlaceholderText('Search documents...');
    fireEvent.change(input, { target: { value: 'test' } });

    await waitFor(() => {
      expect(screen.getByRole('listbox')).toBeInTheDocument();
    });
  });

  it('handles suggestion click', async () => {
    const onSearch = jest.fn();
    renderWithProviders(<SearchInput onSearch={onSearch} />);
    
    const input = screen.getByPlaceholderText('Search documents...');
    fireEvent.change(input, { target: { value: 'test' } });

    await waitFor(() => {
      const suggestion = screen.getByText('test suggestion');
      fireEvent.click(suggestion);
    });

    expect(onSearch).toHaveBeenCalledWith('test suggestion');
  });
}); 