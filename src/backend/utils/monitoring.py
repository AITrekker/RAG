"""
Performance Monitoring and Alerting for the Enterprise RAG Platform.

This module provides a `ResponseTimeMonitor` class that is responsible for
tracking the performance of various components within the application.
It records metrics such as duration, success/failure of operations, and
associated metadata.

Key features include:
- A central, thread-safe monitor for recording performance metrics.
- In-memory storage of recent metrics using a deque for efficiency.
- Calculation of performance statistics (e.g., average, median, min/max duration).
- A simple alerting mechanism for when operations exceed defined thresholds.
- Singleton management to ensure a single monitor instance is used application-wide.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import statistics
import threading
import json

# Internal imports
from ..config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Individual performance measurement"""
    component: str
    operation: str
    duration: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


@dataclass
class PerformanceAlert:
    """Performance alert when thresholds are exceeded"""
    alert_type: str
    component: str
    metric: str
    threshold: float
    actual_value: float
    timestamp: datetime
    severity: str = "warning"  # "info", "warning", "error", "critical"
    message: str = ""


class ResponseTimeMonitor:
    """
    Comprehensive response time monitoring for RAG platform
    Tracks performance across all components with alerting
    """
    
    def __init__(
        self,
        max_history_size: int = 10000,
        alert_thresholds: Optional[Dict[str, float]] = None,
        enable_alerts: bool = True
    ):
        """
        Initialize response time monitor
        
        Args:
            max_history_size: Maximum number of metrics to keep in memory
            alert_thresholds: Component-specific alert thresholds (seconds)
            enable_alerts: Whether to generate alerts
        """
        self.max_history_size = max_history_size
        self.enable_alerts = enable_alerts
        
        # Default alert thresholds (in seconds)
        self.alert_thresholds = {
            "embedding_generation": 5.0,
            "similarity_search": 3.0,
            "llm_generation": 10.0,
            "query_processing": 15.0,
            "document_indexing": 30.0,
            "rag_pipeline": 20.0,
            **( alert_thresholds or {})
        }
        
        # Storage for metrics
        self.metrics_history: deque = deque(maxlen=max_history_size)
        self.component_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.alerts: deque = deque(maxlen=1000)
        
        # Performance statistics
        self.stats_cache = {}
        self.stats_cache_time = None
        self.stats_cache_ttl = 60  # Cache for 60 seconds
        
        # Thread safety
        self._lock = threading.Lock()
        
        logger.info("Response time monitor initialized")
        logger.info(f"Alert thresholds: {self.alert_thresholds}")
    
    def record_metric(
        self,
        component: str,
        operation: str,
        duration: float,
        metadata: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """
        Record a performance metric
        
        Args:
            component: Component name (e.g., "embedding_service", "llm_service")
            operation: Operation name (e.g., "encode_text", "generate_response")
            duration: Time taken in seconds
            metadata: Additional metadata
            success: Whether the operation succeeded
            error: Error message if failed
        """
        with self._lock:
            timestamp = datetime.now()
            
            metric = PerformanceMetric(
                component=component,
                operation=operation,
                duration=duration,
                timestamp=timestamp,
                metadata=metadata or {},
                success=success,
                error=error
            )
            
            # Store in history
            self.metrics_history.append(metric)
            self.component_metrics[component].append(metric)
            
            # Check for alerts (simplified for now)
            if self.enable_alerts and success:
                threshold = self.alert_thresholds.get(component, 10.0)
                if duration > threshold:
                    logger.warning(f"Performance alert: {component}.{operation} took {duration:.3f}s (threshold: {threshold:.3f}s)")
            
            # Invalidate stats cache
            self.stats_cache_time = None
            
            logger.debug(f"Recorded metric: {component}.{operation} = {duration:.3f}s")
    
    def get_overall_stats(self, time_window: Optional[timedelta] = None) -> Dict[str, Any]:
        """Get overall performance statistics"""
        if (self.stats_cache_time and 
            datetime.now() - self.stats_cache_time < timedelta(seconds=self.stats_cache_ttl)):
            return self.stats_cache
        
        time_window = time_window or timedelta(hours=1)
        cutoff_time = datetime.now() - time_window
        
        # Filter metrics by time window
        recent_metrics = [
            m for m in self.metrics_history
            if m.timestamp >= cutoff_time
        ]
        
        if not recent_metrics:
            return {
                "time_window": str(time_window),
                "total_operations": 0,
                "success_rate": 0.0,
                "average_duration": 0.0,
                "components": {},
                "alerts_count": 0
            }
        
        # Overall statistics
        durations = [m.duration for m in recent_metrics]
        successful_ops = sum(1 for m in recent_metrics if m.success)
        
        stats = {
            "time_window": str(time_window),
            "total_operations": len(recent_metrics),
            "successful_operations": successful_ops,
            "failed_operations": len(recent_metrics) - successful_ops,
            "success_rate": successful_ops / len(recent_metrics),
            "average_duration": statistics.mean(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "median_duration": statistics.median(durations),
        }
        
        # Cache results
        self.stats_cache = stats
        self.stats_cache_time = datetime.now()
        
        return stats


# Global monitor instance
_performance_monitor: Optional[ResponseTimeMonitor] = None


def get_performance_monitor(force_reload: bool = False, **kwargs) -> ResponseTimeMonitor:
    """
    Get or create global performance monitor
    
    Args:
        force_reload: Force creation of new monitor
        **kwargs: Additional arguments for ResponseTimeMonitor
        
    Returns:
        ResponseTimeMonitor instance
    """
    global _performance_monitor
    
    if force_reload or _performance_monitor is None:
        logger.info("Creating new performance monitor")
        _performance_monitor = ResponseTimeMonitor(**kwargs)
    
    return _performance_monitor


def record_embedding_time(duration: float, model_name: str, batch_size: int = 1) -> None:
    """Record embedding generation time"""
    monitor = get_performance_monitor()
    monitor.record_metric(
        component="embedding_service",
        operation="generate_embeddings",
        duration=duration,
        metadata={"model": model_name, "batch_size": batch_size}
    )


def record_llm_time(duration: float, model_name: str, tokens: int = 0) -> None:
    """Record LLM generation time"""
    monitor = get_performance_monitor()
    monitor.record_metric(
        component="llm_service",
        operation="generate_response",
        duration=duration,
        metadata={"model": model_name, "tokens": tokens}
    )


def record_rag_pipeline_time(duration: float, tenant_id: str, success: bool = True) -> None:
    """Record the total time for a RAG pipeline query."""
    monitor = get_performance_monitor()
    monitor.record_metric(
        component="rag_pipeline",
        operation="query",
        duration=duration,
        metadata={"tenant_id": tenant_id},
        success=success
    )


def get_performance_summary() -> Dict[str, Any]:
    """Get overall performance summary"""
    monitor = get_performance_monitor()
    return monitor.get_overall_stats() 