import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';

interface PerformanceMetrics {
  responseTime: number;
  ttfb: number;  // Time to First Byte
  renderTime: number;
  networkTime: number;
}

interface PerformanceEvent {
  type: 'search' | 'suggestion' | 'render';
  metrics: PerformanceMetrics;
  timestamp: number;
  queryId?: string;
}

const METRICS_ENDPOINT = '/api/metrics';

export function usePerformanceMonitoring() {
  const queryClient = useQueryClient();
  const metricsQueue = useRef<PerformanceEvent[]>([]);
  const flushInterval = useRef<NodeJS.Timeout>();

  // Track response time for API calls
  useEffect(() => {
    const unsubscribe = queryClient.getQueryCache().subscribe((event) => {
      if (event.type === 'updated' && event.query.state.status === 'success') {
        const queryStartTime = event.query.state.dataUpdatedAt;
        const responseTime = Date.now() - queryStartTime;

        const metrics: PerformanceMetrics = {
          responseTime,
          ttfb: performance.now(), // Simplified, should use PerformanceObserver in production
          renderTime: 0, // Will be updated after render
          networkTime: responseTime,
        };

        metricsQueue.current.push({
          type: event.query.queryKey[0] as 'search' | 'suggestion',
          metrics,
          timestamp: Date.now(),
          queryId: event.query.queryHash,
        });
      }
    });

    return () => {
      unsubscribe();
    };
  }, [queryClient]);

  // Track render time using PerformanceObserver
  useEffect(() => {
    if (typeof window !== 'undefined' && 'PerformanceObserver' in window) {
      const observer = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        entries.forEach((entry) => {
          if (entry.entryType === 'render') {
            metricsQueue.current.push({
              type: 'render',
              metrics: {
                responseTime: 0,
                ttfb: 0,
                renderTime: entry.duration,
                networkTime: 0,
              },
              timestamp: Date.now(),
            });
          }
        });
      });

      observer.observe({ entryTypes: ['render'] });
      return () => observer.disconnect();
    }
  }, []);

  // Flush metrics to server periodically
  useEffect(() => {
    const flushMetrics = async () => {
      if (metricsQueue.current.length > 0) {
        try {
          const metrics = [...metricsQueue.current];
          metricsQueue.current = [];

          await fetch(METRICS_ENDPOINT, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(metrics),
          });
        } catch (error) {
          console.error('Failed to flush metrics:', error);
          // Restore metrics to queue on failure
          metricsQueue.current = [...metricsQueue.current, ...metricsQueue.current];
        }
      }
    };

    flushInterval.current = setInterval(flushMetrics, 5000);
    return () => {
      if (flushInterval.current) {
        clearInterval(flushInterval.current);
      }
    };
  }, []);

  return {
    logMetric: (type: 'search' | 'suggestion' | 'render', metrics: Partial<PerformanceMetrics>) => {
      metricsQueue.current.push({
        type,
        metrics: {
          responseTime: 0,
          ttfb: 0,
          renderTime: 0,
          networkTime: 0,
          ...metrics,
        },
        timestamp: Date.now(),
      });
    },
  };
} 