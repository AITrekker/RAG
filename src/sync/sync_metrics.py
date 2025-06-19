"""
Sync metrics collection and tracking system.

This module provides functionality for collecting, aggregating, and analyzing
sync task metrics with tenant isolation.
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json

from ..db.models import SyncMetric, SyncTaskStatus
from ..db.operations import get_session
from .sync_state import SyncState

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Types of sync metrics to track."""
    SYNC_TIME = "sync_time"
    SUCCESS_RATE = "success_rate"
    ERROR_RATE = "error_rate"
    FILE_COUNT = "file_count"
    BYTES_PROCESSED = "bytes_processed"
    RETRY_COUNT = "retry_count"
    DELETION_COUNT = "deletion_count"

@dataclass
class MetricValue:
    """Represents a metric value with timestamp and metadata."""
    value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

class MetricsCollector:
    """Collects and manages sync task metrics."""
    
    def __init__(self, tenant_id: Optional[str] = None):
        """Initialize metrics collector.
        
        Args:
            tenant_id: Optional tenant identifier for isolation
        """
        self.tenant_id = tenant_id
        self._metrics: Dict[str, Dict[MetricType, List[MetricValue]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._start_times: Dict[str, datetime] = {}
    
    def start_task(self, task_id: str):
        """Start timing a sync task.
        
        Args:
            task_id: Unique task identifier
        """
        self._start_times[task_id] = datetime.now(timezone.utc)
        logger.debug(f"Started timing task {task_id}")
    
    def end_task(
        self,
        task_id: str,
        status: SyncTaskStatus,
        file_count: int,
        bytes_processed: int,
        retry_count: int = 0,
        deletion_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """End timing a sync task and record metrics.
        
        Args:
            task_id: Task identifier
            status: Task completion status
            file_count: Number of files processed
            bytes_processed: Total bytes processed
            retry_count: Number of retries (default: 0)
            deletion_count: Number of deletions (default: 0)
            metadata: Optional additional metadata
        """
        if task_id not in self._start_times:
            logger.warning(f"No start time found for task {task_id}")
            return
        
        end_time = datetime.now(timezone.utc)
        duration = (end_time - self._start_times[task_id]).total_seconds()
        
        # Record metrics
        self.record_metric(
            task_id,
            MetricType.SYNC_TIME,
            duration,
            metadata
        )
        
        self.record_metric(
            task_id,
            MetricType.SUCCESS_RATE,
            1.0 if status == SyncTaskStatus.SUCCESS else 0.0,
            metadata
        )
        
        self.record_metric(
            task_id,
            MetricType.ERROR_RATE,
            1.0 if status == SyncTaskStatus.ERROR else 0.0,
            metadata
        )
        
        self.record_metric(
            task_id,
            MetricType.FILE_COUNT,
            file_count,
            metadata
        )
        
        self.record_metric(
            task_id,
            MetricType.BYTES_PROCESSED,
            bytes_processed,
            metadata
        )
        
        self.record_metric(
            task_id,
            MetricType.RETRY_COUNT,
            retry_count,
            metadata
        )
        
        self.record_metric(
            task_id,
            MetricType.DELETION_COUNT,
            deletion_count,
            metadata
        )
        
        # Clean up
        del self._start_times[task_id]
        
        logger.debug(
            f"Recorded metrics for task {task_id}: "
            f"duration={duration:.2f}s, status={status.value}"
        )
    
    def record_metric(
        self,
        task_id: str,
        metric_type: MetricType,
        value: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a single metric value.
        
        Args:
            task_id: Task identifier
            metric_type: Type of metric
            value: Metric value
            metadata: Optional metadata
        """
        metric_value = MetricValue(
            value=value,
            metadata=metadata or {}
        )
        self._metrics[task_id][metric_type].append(metric_value)
        
        # Persist metric to database
        with get_session() as session:
            metric = SyncMetric(
                task_id=task_id,
                tenant_id=self.tenant_id,
                metric_type=metric_type.value,
                value=value,
                timestamp=metric_value.timestamp,
                metadata=json.dumps(metadata) if metadata else None
            )
            session.add(metric)
            session.commit()
    
    def get_task_metrics(
        self,
        task_id: str,
        metric_type: Optional[MetricType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[MetricType, List[MetricValue]]:
        """Get metrics for a specific task.
        
        Args:
            task_id: Task identifier
            metric_type: Optional metric type filter
            start_time: Optional start time filter
            end_time: Optional end time filter
        
        Returns:
            Dictionary of metric types to lists of values
        """
        if task_id not in self._metrics:
            return {}
        
        metrics = self._metrics[task_id]
        if metric_type:
            metrics = {metric_type: metrics.get(metric_type, [])}
        
        if start_time or end_time:
            filtered_metrics = {}
            for mtype, values in metrics.items():
                filtered_values = [
                    v for v in values
                    if (not start_time or v.timestamp >= start_time)
                    and (not end_time or v.timestamp <= end_time)
                ]
                if filtered_values:
                    filtered_metrics[mtype] = filtered_values
            metrics = filtered_metrics
        
        return metrics
    
    def get_aggregate_metrics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[MetricType, Tuple[float, float, float]]:
        """Get aggregate metrics across all tasks.
        
        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter
        
        Returns:
            Dictionary of metric types to tuples of (min, max, avg)
        """
        aggregates = {}
        
        for metric_type in MetricType:
            values = []
            for task_metrics in self._metrics.values():
                if metric_type not in task_metrics:
                    continue
                
                task_values = task_metrics[metric_type]
                if start_time or end_time:
                    task_values = [
                        v for v in task_values
                        if (not start_time or v.timestamp >= start_time)
                        and (not end_time or v.timestamp <= end_time)
                    ]
                
                values.extend(v.value for v in task_values)
            
            if values:
                aggregates[metric_type] = (
                    min(values),
                    max(values),
                    sum(values) / len(values)
                )
        
        return aggregates
    
    def cleanup_old_metrics(self, retention_days: int = 30):
        """Clean up metrics older than retention period.
        
        Args:
            retention_days: Number of days to retain metrics
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        # Clean up in-memory metrics
        for task_id in list(self._metrics.keys()):
            for metric_type in list(self._metrics[task_id].keys()):
                self._metrics[task_id][metric_type] = [
                    v for v in self._metrics[task_id][metric_type]
                    if v.timestamp >= cutoff
                ]
                
                if not self._metrics[task_id][metric_type]:
                    del self._metrics[task_id][metric_type]
            
            if not self._metrics[task_id]:
                del self._metrics[task_id]
        
        # Clean up database metrics
        with get_session() as session:
            session.query(SyncMetric).filter(
                SyncMetric.timestamp < cutoff
            ).delete()
            session.commit()
        
        logger.info(f"Cleaned up metrics older than {retention_days} days") 