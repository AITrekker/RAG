import React from 'react';
import { Box, Rating, Tooltip } from '@mui/material';

export interface RelevanceIndicatorProps {
  score: number; // Score between 0 and 1
  size?: 'small' | 'medium' | 'large';
}

export function RelevanceIndicator({ score, size = 'medium' }: RelevanceIndicatorProps) {
  // Convert score from 0-1 to 0-5 for star rating
  const starScore = Math.round(score * 5);
  const percentage = Math.round(score * 100);

  return (
    <Tooltip title={`Relevance: ${percentage}%`} arrow>
      <Box>
        <Rating
          value={starScore}
          readOnly
          size={size}
          className="text-blue-500"
        />
      </Box>
    </Tooltip>
  );
} 