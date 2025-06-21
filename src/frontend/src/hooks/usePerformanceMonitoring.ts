import { useCallback, useRef } from 'react';

interface PerformanceMetric {
  name: string;
  duration: number;
  timestamp: number;
  type: 'navigation' | 'interaction' | 'api' | 'render';
}

interface PerformanceHookReturn {
  measureInteraction: (name: string, fn: () => Promise<void> | void) => Promise<void>;
  measureRender: (name: string, fn: () => void) => void;
  getMetrics: () => PerformanceMetric[];
  clearMetrics: () => void;
}

export const usePerformanceMonitoring = (): PerformanceHookReturn => {
  const metricsRef = useRef<PerformanceMetric[]>([]);

  const addMetric = useCallback((metric: PerformanceMetric) => {
    metricsRef.current.push(metric);
    
    // Log performance warnings
    if (metric.duration > 500 && metric.type === 'interaction') {
      console.warn(`Slow interaction detected: ${metric.name} took ${metric.duration}ms`);
    }
    
    // Keep only last 100 metrics to prevent memory leaks
    if (metricsRef.current.length > 100) {
      metricsRef.current = metricsRef.current.slice(-100);
    }
  }, []);

  const measureInteraction = useCallback(async (name: string, fn: () => Promise<void> | void) => {
    const startTime = performance.now();
    
    try {
      await fn();
    } finally {
      const endTime = performance.now();
      const duration = endTime - startTime;
      
      addMetric({
        name,
        duration,
        timestamp: Date.now(),
        type: 'interaction'
      });
    }
  }, [addMetric]);

  const measureRender = useCallback((name: string, fn: () => void) => {
    const startTime = performance.now();
    
    fn();
    
    const endTime = performance.now();
    const duration = endTime - startTime;
    
    addMetric({
      name,
      duration,
      timestamp: Date.now(),
      type: 'render'
    });
  }, [addMetric]);

  const getMetrics = useCallback(() => {
    return [...metricsRef.current];
  }, []);

  const clearMetrics = useCallback(() => {
    metricsRef.current = [];
  }, []);

  return {
    measureInteraction,
    measureRender,
    getMetrics,
    clearMetrics
  };
}; 