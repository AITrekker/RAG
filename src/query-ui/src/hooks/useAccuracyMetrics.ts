import { useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';

interface AccuracyMetrics {
  queryId: string;
  relevanceScore: number;
  citationAccuracy: number;
  answerCompleteness: number;
  userRating?: number;
  feedback?: string;
}

const ACCURACY_ENDPOINT = '/api/metrics/accuracy';

export function useAccuracyMetrics() {
  const { mutate: submitMetrics } = useMutation({
    mutationFn: async (metrics: AccuracyMetrics) => {
      const response = await fetch(ACCURACY_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(metrics),
      });

      if (!response.ok) {
        throw new Error('Failed to submit accuracy metrics');
      }

      return response.json();
    },
  });

  const logAccuracy = useCallback((metrics: AccuracyMetrics) => {
    submitMetrics(metrics);
  }, [submitMetrics]);

  const calculateRelevanceScore = useCallback((results: any[]) => {
    if (!results.length) return 0;
    
    return results.reduce((acc, result) => {
      return acc + (result.relevanceScore || 0);
    }, 0) / results.length;
  }, []);

  const calculateCitationAccuracy = useCallback((citations: any[]) => {
    if (!citations.length) return 0;

    return citations.reduce((acc, citation) => {
      return acc + (citation.isValid ? 1 : 0);
    }, 0) / citations.length;
  }, []);

  const calculateAnswerCompleteness = useCallback((answer: string, expectedKeywords: string[]) => {
    if (!expectedKeywords.length) return 1;

    const lowerAnswer = answer.toLowerCase();
    const foundKeywords = expectedKeywords.filter(keyword => 
      lowerAnswer.includes(keyword.toLowerCase())
    );

    return foundKeywords.length / expectedKeywords.length;
  }, []);

  return {
    logAccuracy,
    calculateRelevanceScore,
    calculateCitationAccuracy,
    calculateAnswerCompleteness,
  };
} 