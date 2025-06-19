import React, { useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Rating,
  TextField,
  Tooltip,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import ThumbDownIcon from '@mui/icons-material/ThumbDown';
import { useMutation, UseMutationResult } from '@tanstack/react-query';

interface FeedbackCollectorProps {
  queryId: string;
  onFeedbackSubmitted?: () => void;
}

interface FeedbackData {
  queryId: string;
  rating: number;
  feedback: string;
}

const FEEDBACK_ENDPOINT = '/api/feedback';

export function FeedbackCollector({ queryId, onFeedbackSubmitted }: FeedbackCollectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [rating, setRating] = useState<number | null>(null);
  const [feedback, setFeedback] = useState('');
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const { mutate: submitFeedback, isPending } = useMutation<unknown, Error, FeedbackData>({
    mutationFn: async (data) => {
      const response = await fetch(FEEDBACK_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        throw new Error('Failed to submit feedback');
      }

      return response.json();
    },
    onSuccess: () => {
      setIsOpen(false);
      setRating(null);
      setFeedback('');
      onFeedbackSubmitted?.();
    },
  });

  const handleSubmit = () => {
    if (rating !== null) {
      submitFeedback({
        queryId,
        rating,
        feedback,
      });
    }
  };

  return (
    <>
      <Box className="flex items-center gap-2">
        <Tooltip title="Was this result helpful?">
          <IconButton
            onClick={() => {
              setRating(5);
              setIsOpen(true);
            }}
            size={isMobile ? 'small' : 'medium'}
          >
            <ThumbUpIcon />
          </IconButton>
        </Tooltip>
        <Tooltip title="Was this result not helpful?">
          <IconButton
            onClick={() => {
              setRating(1);
              setIsOpen(true);
            }}
            size={isMobile ? 'small' : 'medium'}
          >
            <ThumbDownIcon />
          </IconButton>
        </Tooltip>
      </Box>

      <Dialog
        open={isOpen}
        onClose={() => !isPending && setIsOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Your Feedback</DialogTitle>
        <DialogContent>
          <Box className="flex flex-col gap-4 py-4">
            <Box className="flex items-center gap-2">
              <span>Rating:</span>
              <Rating
                value={rating}
                onChange={(_, newValue) => setRating(newValue)}
                disabled={isPending}
              />
            </Box>
            <TextField
              label="Additional Feedback"
              multiline
              rows={4}
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              disabled={isPending}
              fullWidth
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setIsOpen(false)}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isPending || rating === null}
            variant="contained"
          >
            Submit
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
} 