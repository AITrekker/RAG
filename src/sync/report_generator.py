"""
Report generation from sync metrics.

This module provides functionality for generating comprehensive sync reports
from collected metrics with aggregation and analysis capabilities.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json

from ..db.models import SyncTaskStatus
from .sync_metrics import MetricType, MetricsCollector
from .report_storage import ReportStorage, SyncReport

logger = logging.getLogger(__name__)

@dataclass
class ReportSummary:
    """Summary statistics for a collection of sync reports."""
    total_tasks: int
    success_count: int
    error_count: int
    avg_sync_time: float
    total_files: int
    total_bytes: int
    success_rate: float

class ReportGenerator:
    """Generates sync reports from collected metrics."""
    
    def __init__(
        self,
        metrics_collector: MetricsCollector,
        report_storage: ReportStorage
    ):
        """Initialize report generator.
        
        Args:
            metrics_collector: Metrics collector instance
            report_storage: Report storage instance
        """
        self.metrics_collector = metrics_collector
        self.report_storage = report_storage
    
    def generate_task_report(
        self,
        task_id: str,
        tenant_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> SyncReport:
        """Generate a report for a specific task.
        
        Args:
            task_id: Task identifier
            tenant_id: Optional tenant identifier
            details: Optional additional report details
        
        Returns:
            Generated sync report
        """
        metrics = self.metrics_collector.get_task_metrics(task_id)
        
        # Determine task status
        success_metrics = metrics.get(MetricType.SUCCESS_RATE, [])
        error_metrics = metrics.get(MetricType.ERROR_RATE, [])
        
        if success_metrics and success_metrics[-1].value == 1.0:
            status = SyncTaskStatus.SUCCESS
        elif error_metrics and error_metrics[-1].value == 1.0:
            status = SyncTaskStatus.ERROR
        else:
            status = SyncTaskStatus.IN_PROGRESS
        
        # Create report
        report = SyncReport(
            task_id=task_id,
            tenant_id=tenant_id,
            timestamp=datetime.now(timezone.utc),
            status=status,
            metrics=metrics,
            details=details or {}
        )
        
        # Store report
        self.report_storage.store_report(report)
        logger.info(f"Generated report for task {task_id}")
        
        return report
    
    def generate_summary_report(
        self,
        tenant_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> ReportSummary:
        """Generate a summary report for all tasks in a time period.
        
        Args:
            tenant_id: Optional tenant filter
            start_time: Optional start time
            end_time: Optional end time
        
        Returns:
            Report summary statistics
        """
        reports = self.report_storage.get_reports(
            tenant_id=tenant_id,
            start_time=start_time,
            end_time=end_time
        )
        
        if not reports:
            return ReportSummary(
                total_tasks=0,
                success_count=0,
                error_count=0,
                avg_sync_time=0.0,
                total_files=0,
                total_bytes=0,
                success_rate=0.0
            )
        
        # Calculate statistics
        success_count = sum(
            1 for r in reports
            if r.status == SyncTaskStatus.SUCCESS
        )
        error_count = sum(
            1 for r in reports
            if r.status == SyncTaskStatus.ERROR
        )
        
        sync_times = []
        total_files = 0
        total_bytes = 0
        
        for report in reports:
            for metric_type, values in report.metrics.items():
                if not values:
                    continue
                
                if metric_type == MetricType.SYNC_TIME:
                    sync_times.append(values[-1].value)
                elif metric_type == MetricType.FILE_COUNT:
                    total_files += values[-1].value
                elif metric_type == MetricType.BYTES_PROCESSED:
                    total_bytes += values[-1].value
        
        avg_sync_time = (
            sum(sync_times) / len(sync_times)
            if sync_times else 0.0
        )
        
        success_rate = (
            success_count / len(reports)
            if reports else 0.0
        )
        
        return ReportSummary(
            total_tasks=len(reports),
            success_count=success_count,
            error_count=error_count,
            avg_sync_time=avg_sync_time,
            total_files=total_files,
            total_bytes=total_bytes,
            success_rate=success_rate
        )
    
    def generate_trend_analysis(
        self,
        tenant_id: Optional[str] = None,
        days: int = 30,
        interval_hours: int = 24
    ) -> Dict[str, List[Tuple[datetime, float]]]:
        """Generate trend analysis for key metrics.
        
        Args:
            tenant_id: Optional tenant filter
            days: Number of days to analyze
            interval_hours: Interval size in hours
        
        Returns:
            Dictionary of metric names to lists of (timestamp, value) pairs
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)
        
        reports = self.report_storage.get_reports(
            tenant_id=tenant_id,
            start_time=start_time,
            end_time=end_time
        )
        
        # Group reports by time interval
        intervals: Dict[datetime, List[SyncReport]] = {}
        interval_delta = timedelta(hours=interval_hours)
        
        current_interval = start_time
        while current_interval <= end_time:
            next_interval = current_interval + interval_delta
            
            interval_reports = [
                r for r in reports
                if current_interval <= r.timestamp < next_interval
            ]
            
            if interval_reports:
                intervals[current_interval] = interval_reports
            
            current_interval = next_interval
        
        # Calculate trends
        trends: Dict[str, List[Tuple[datetime, float]]] = {
            "success_rate": [],
            "avg_sync_time": [],
            "avg_file_count": [],
            "avg_bytes_processed": []
        }
        
        for interval_start, interval_reports in intervals.items():
            # Success rate
            success_count = sum(
                1 for r in interval_reports
                if r.status == SyncTaskStatus.SUCCESS
            )
            success_rate = success_count / len(interval_reports)
            trends["success_rate"].append(
                (interval_start, success_rate)
            )
            
            # Average metrics
            sync_times = []
            file_counts = []
            bytes_processed = []
            
            for report in interval_reports:
                for metric_type, values in report.metrics.items():
                    if not values:
                        continue
                    
                    if metric_type == MetricType.SYNC_TIME:
                        sync_times.append(values[-1].value)
                    elif metric_type == MetricType.FILE_COUNT:
                        file_counts.append(values[-1].value)
                    elif metric_type == MetricType.BYTES_PROCESSED:
                        bytes_processed.append(values[-1].value)
            
            if sync_times:
                trends["avg_sync_time"].append(
                    (interval_start, sum(sync_times) / len(sync_times))
                )
            
            if file_counts:
                trends["avg_file_count"].append(
                    (interval_start, sum(file_counts) / len(file_counts))
                )
            
            if bytes_processed:
                trends["avg_bytes_processed"].append(
                    (interval_start, sum(bytes_processed) / len(bytes_processed))
                )
        
        return trends 