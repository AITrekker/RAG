import React from 'react';
import {
  Typography,
  IconButton,
  Tooltip,
  Chip,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';

export interface SourceCitationProps {
  source: string;
  metadata: {
    path?: string;
    lineNumbers?: string;
    timestamp?: string;
    type?: string;
    [key: string]: any;
  };
  size?: 'small' | 'medium' | 'large';
}

export function SourceCitation({ source, metadata, size = 'medium' }: SourceCitationProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const handleCopy = () => {
    const text = `${source}${metadata.path ? ` (${metadata.path})` : ''}${
      metadata.lineNumbers ? ` lines ${metadata.lineNumbers}` : ''
    }`;
    navigator.clipboard.writeText(text);
  };

  const handleOpen = () => {
    if (metadata.path) {
      // You can implement custom file opening logic here
      console.log('Opening:', metadata.path);
    }
  };

  const formatTimestamp = (timestamp?: string) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return isMobile
      ? date.toLocaleDateString()
      : date.toLocaleString();
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Typography
        variant="body2"
        component="span"
        className={`text-gray-600 ${size === 'small' ? 'text-sm' : ''}`}
      >
        {source}
        {metadata.path && (
          <span className="ml-1 text-gray-400">
            ({metadata.path}
            {metadata.lineNumbers && ` lines ${metadata.lineNumbers}`})
          </span>
        )}
      </Typography>

      <div className="flex items-center gap-1">
        {metadata.timestamp && (
          <Chip
            label={formatTimestamp(metadata.timestamp)}
            size={size === 'small' ? 'small' : 'medium'}
            className="bg-gray-100"
          />
        )}
        {metadata.type && (
          <Chip
            label={metadata.type}
            size={size === 'small' ? 'small' : 'medium'}
            className="bg-gray-100"
          />
        )}
        <Tooltip title="Copy citation">
          <IconButton
            onClick={handleCopy}
            size={size === 'small' ? 'small' : 'medium'}
            className="text-gray-400 hover:text-gray-600"
          >
            <ContentCopyIcon fontSize={size === 'small' ? 'small' : 'medium'} />
          </IconButton>
        </Tooltip>
        {metadata.path && (
          <Tooltip title="Open source">
            <IconButton
              onClick={handleOpen}
              size={size === 'small' ? 'small' : 'medium'}
              className="text-gray-400 hover:text-gray-600"
            >
              <OpenInNewIcon fontSize={size === 'small' ? 'small' : 'medium'} />
            </IconButton>
          </Tooltip>
        )}
      </div>
    </div>
  );
} 