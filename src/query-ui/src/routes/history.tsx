import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Button,
  Paper,
  CircularProgress,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import DeleteIcon from '@mui/icons-material/Delete';
import { useSearchHistory } from '../hooks/useSearchHistory';

export function Component() {
  const navigate = useNavigate();
  const { history, isLoading, clearHistory, isClearing } = useSearchHistory();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const handleSearch = (query: string) => {
    navigate(`/search?q=${encodeURIComponent(query)}`);
  };

  const formatTimestamp = (timestamp: string) => {
    if (isMobile) {
      return new Date(timestamp).toLocaleDateString();
    }
    return new Date(timestamp).toLocaleString();
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <CircularProgress />
      </div>
    );
  }

  return (
    <div className={`py-4 ${isMobile ? 'px-2' : 'py-8'}`}>
      <div className="max-w-3xl mx-auto">
        <div className="flex justify-between items-center mb-4 sm:mb-6">
          <Typography
            variant={isMobile ? 'h5' : 'h4'}
            component="h1"
            className="flex-shrink-0"
          >
            Search History
          </Typography>
          <Button
            variant="outlined"
            color="error"
            onClick={() => clearHistory()}
            disabled={isClearing || history.length === 0}
            size={isMobile ? 'small' : 'medium'}
          >
            Clear History
          </Button>
        </div>

        <Paper>
          <List>
            {history.length === 0 ? (
              <ListItem>
                <ListItemText
                  primary="No search history"
                  secondary="Your recent searches will appear here"
                />
              </ListItem>
            ) : (
              history.map((entry) => (
                <ListItem key={entry.id}>
                  <ListItemText
                    primary={
                      <Typography
                        variant="body1"
                        className={isMobile ? 'text-sm' : ''}
                        noWrap
                      >
                        {entry.query}
                      </Typography>
                    }
                    secondary={
                      <Typography
                        variant="body2"
                        className={`text-gray-600 ${isMobile ? 'text-xs' : ''}`}
                      >
                        {formatTimestamp(entry.timestamp)}
                        {entry.resultCount !== undefined &&
                          ` • ${entry.resultCount} results`}
                      </Typography>
                    }
                  />
                  <ListItemSecondaryAction>
                    <IconButton
                      edge="end"
                      aria-label="search"
                      onClick={() => handleSearch(entry.query)}
                      size={isMobile ? 'small' : 'medium'}
                    >
                      <SearchIcon />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              ))
            )}
          </List>
        </Paper>
      </div>
    </div>
  );
}

export default Component; 