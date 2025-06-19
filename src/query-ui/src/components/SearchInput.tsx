import React, { useState, useEffect, useRef } from 'react';
import {
  Paper,
  InputBase,
  IconButton,
  Popper,
  List,
  ListItemButton,
  ListItemText,
  CircularProgress,
  useTheme,
  useMediaQuery,
  FormHelperText,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import { useSearchSuggestions } from '../hooks/useSearchSuggestions';
import { useSearchForm, SearchFormData } from '../hooks/useSearchForm';
import { SearchSuggestion } from '../types/search';

interface SearchInputProps {
  onSearch: (query: string) => void;
}

export function SearchInput({ onSearch }: SearchInputProps) {
  const [isOpen, setIsOpen] = useState(false);
  const anchorRef = useRef<HTMLDivElement>(null);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const {
    form: {
      register,
      watch,
      setValue,
      formState: { errors },
      handleSubmit,
    },
  } = useSearchForm();

  const query = watch('query');
  const { data: suggestions = [], isLoading } = useSearchSuggestions(query);

  useEffect(() => {
    setIsOpen(Boolean(query && suggestions.length > 0));
  }, [query, suggestions]);

  const onFormSubmit = handleSubmit((data: SearchFormData) => {
    if (data.query.trim()) {
      onSearch(data.query.trim());
      setIsOpen(false);
    }
  });

  const handleSuggestionClick = (suggestion: SearchSuggestion) => {
    const searchText = typeof suggestion === 'string' ? suggestion : suggestion.text;
    setValue('query', searchText);
    onSearch(searchText);
    setIsOpen(false);
  };

  return (
    <div ref={anchorRef}>
      <Paper
        component="form"
        onSubmit={onFormSubmit}
        className={`flex items-center ${isMobile ? 'p-1' : 'p-2'}`}
        elevation={1}
      >
        <InputBase
          {...register('query')}
          placeholder="Search documents..."
          className={`ml-2 flex-grow ${isMobile ? 'text-sm' : ''}`}
          inputProps={{ 'aria-label': 'search documents' }}
          autoComplete="off"
          size={isMobile ? 'small' : 'medium'}
          error={Boolean(errors.query)}
        />
        {isLoading ? (
          <CircularProgress size={24} className="mx-2" />
        ) : (
          <IconButton type="submit" aria-label="search" size={isMobile ? 'small' : 'medium'}>
            <SearchIcon />
          </IconButton>
        )}
      </Paper>
      {errors.query && (
        <FormHelperText error className="ml-2 mt-1">
          {errors.query.message}
        </FormHelperText>
      )}

      <Popper
        open={isOpen}
        anchorEl={anchorRef.current}
        placement="bottom-start"
        className="z-10 w-full max-w-3xl"
      >
        <Paper className="mt-1">
          <List>
            {suggestions.map((suggestion: SearchSuggestion, index: number) => (
              <ListItemButton
                key={index}
                onClick={() => handleSuggestionClick(suggestion)}
                className={isMobile ? 'py-1' : 'py-2'}
              >
                <ListItemText
                  primary={typeof suggestion === 'string' ? suggestion : suggestion.text}
                  primaryTypographyProps={{
                    className: isMobile ? 'text-sm' : '',
                    noWrap: true,
                  }}
                />
              </ListItemButton>
            ))}
          </List>
        </Paper>
      </Popper>
    </div>
  );
} 