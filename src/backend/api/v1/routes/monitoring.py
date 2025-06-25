"""
System Monitoring API Routes

This module provides API endpoints for system monitoring,
performance metrics, and error tracking.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta

from src.backend.utils.monitoring import (
    get_logger,
    ErrorTracker,
    PerformanceMonitor,
    SystemMonitor
)
from src.backend.models.api_models import (
    SystemMetricsDetailResponse,
    PerformanceMetricsResponse,
    ErrorLogResponse,
    ErrorLogListResponse
)
from src.backend.middleware.auth import get_current_tenant_id

logger = logging.getLogger(__name__)
router = APIRouter()

# Global instances (these should be initialized in the monitoring module)
error_tracker = ErrorTracker()
performance_monitor = PerformanceMonitor()
system_monitor = SystemMonitor()


@router.get("/metrics/system", response_model=SystemMetricsDetailResponse)
async def get_system_metrics():
    """Get detailed system metrics including CPU, memory, disk, and GPU usage."""
    try:
        metrics = system_monitor.collect_system_metrics()
        
        # Get network and disk I/O stats
        import psutil
        network_io = psutil.net_io_counters()
        disk_io = psutil.disk_io_counters()
        
        return SystemMetricsDetailResponse(
            timestamp=metrics.timestamp,
            cpu_percent=metrics.cpu_percent,
            memory_percent=metrics.memory_percent,
            disk_usage_percent=metrics.disk_usage_percent,
            gpu_utilization=metrics.gpu_utilization,
            gpu_memory_percent=metrics.gpu_memory_percent,
            active_connections=metrics.active_connections,
            network_io={
                "bytes_sent": network_io.bytes_sent if network_io else 0,
                "bytes_recv": network_io.bytes_recv if network_io else 0,
                "packets_sent": network_io.packets_sent if network_io else 0,
                "packets_recv": network_io.packets_recv if network_io else 0
            },
            disk_io={
                "read_bytes": disk_io.read_bytes if disk_io else 0,
                "write_bytes": disk_io.write_bytes if disk_io else 0,
                "read_count": disk_io.read_count if disk_io else 0,
                "write_count": disk_io.write_count if disk_io else 0
            }
        )
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system metrics")


@router.get("/metrics/performance", response_model=PerformanceMetricsResponse)
async def get_performance_metrics(
    hours: int = Query(1, ge=1, le=24, description="Hours of data to retrieve")
):
    """Get performance metrics for the system."""
    try:
        # Get performance metrics summary
        metrics_summary = performance_monitor.get_metrics_summary(hours=hours)
        
        # Calculate derived metrics
        queries_per_minute = metrics_summary.get("queries_per_minute", 0.0)
        average_query_time = metrics_summary.get("average_query_time", 0.0)
        embedding_requests_per_minute = metrics_summary.get("embedding_requests_per_minute", 0.0)
        sync_operations_per_minute = metrics_summary.get("sync_operations_per_minute", 0.0)
        error_rate = metrics_summary.get("error_rate", 0.0)
        
        # Get active tenants count (this would need to be implemented)
        active_tenants = 0  # TODO: Implement tenant counting
        
        return PerformanceMetricsResponse(
            timestamp=datetime.utcnow(),
            queries_per_minute=queries_per_minute,
            average_query_time=average_query_time,
            embedding_requests_per_minute=embedding_requests_per_minute,
            sync_operations_per_minute=sync_operations_per_minute,
            error_rate=error_rate,
            active_tenants=active_tenants
        )
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")


@router.get("/errors", response_model=ErrorLogListResponse)
async def get_error_logs(
    hours: int = Query(24, ge=1, le=168, description="Hours of error logs to retrieve"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID")
):
    """Get error logs with optional filtering."""
    try:
        # Get error statistics
        error_stats = error_tracker.get_error_stats(hours=hours)
        
        # Filter errors based on parameters
        recent_errors = error_stats.get("recent_errors", [])
        
        if severity:
            recent_errors = [e for e in recent_errors if e.get("severity") == severity]
        
        if tenant_id:
            recent_errors = [e for e in recent_errors if e.get("tenant_id") == tenant_id]
        
        # Convert to response format
        error_responses = []
        for error in recent_errors:
            error_responses.append(ErrorLogResponse(
                timestamp=datetime.fromisoformat(error["timestamp"]),
                error_type=error["type"],
                error_message=error["message"],
                severity=error["severity"],
                tenant_id=error.get("tenant_id"),
                endpoint=error.get("endpoint")
            ))
        
        return ErrorLogListResponse(
            errors=error_responses,
            total_count=len(error_responses),
            error_types=error_stats.get("error_types", {})
        )
    except Exception as e:
        logger.error(f"Failed to get error logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get error logs")


@router.get("/errors/stats")
async def get_error_statistics(
    hours: int = Query(24, ge=1, le=168, description="Hours of error data to analyze")
):
    """Get error statistics and trends."""
    try:
        error_stats = error_tracker.get_error_stats(hours=hours)
        
        return {
            "total_errors": error_stats.get("total_errors", 0),
            "error_types": error_stats.get("error_types", {}),
            "error_rate_per_hour": error_stats.get("total_errors", 0) / hours,
            "most_common_error": max(error_stats.get("error_types", {}).items(), key=lambda x: x[1]) if error_stats.get("error_types") else None,
            "analysis_period_hours": hours
        }
    except Exception as e:
        logger.error(f"Failed to get error statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get error statistics")


@router.post("/alerts/test")
async def test_alert_system():
    """Test the alert system by triggering a test alert."""
    try:
        # Trigger a test performance alert
        performance_monitor._trigger_alert("test_metric", 100.0, 50.0)
        
        return {
            "message": "Test alert triggered successfully",
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Failed to test alert system: {e}")
        raise HTTPException(status_code=500, detail="Failed to test alert system")


@router.get("/logs/recent")
async def get_recent_logs(
    lines: int = Query(100, ge=1, le=1000, description="Number of log lines to retrieve"),
    level: Optional[str] = Query(None, description="Log level filter")
):
    """Get recent application logs."""
    try:
        # This would need to be implemented to read from log files
        # For now, return a placeholder response
        
        return {
            "message": "Log retrieval not yet implemented",
            "requested_lines": lines,
            "level_filter": level,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Failed to get recent logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recent logs")


@router.post("/monitoring/start")
async def start_monitoring(
    interval_seconds: int = Query(60, ge=10, le=3600, description="Monitoring interval in seconds")
):
    """Start system monitoring with specified interval."""
    try:
        system_monitor.start_monitoring(interval_seconds=interval_seconds)
        
        return {
            "message": "System monitoring started successfully",
            "interval_seconds": interval_seconds,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Failed to start monitoring: {e}")
        raise HTTPException(status_code=500, detail="Failed to start monitoring")


@router.post("/monitoring/stop")
async def stop_monitoring():
    """Stop system monitoring."""
    try:
        system_monitor.stop_monitoring()
        
        return {
            "message": "System monitoring stopped successfully",
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Failed to stop monitoring: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop monitoring")


@router.get("/health")
async def monitoring_health_check():
    """Check the health of the monitoring system."""
    try:
        # Check if monitoring components are working
        monitoring_active = system_monitor.is_monitoring_active if hasattr(system_monitor, 'is_monitoring_active') else False
        
        return {
            "status": "healthy" if monitoring_active else "degraded",
            "monitoring_active": monitoring_active,
            "error_tracker_available": error_tracker is not None,
            "performance_monitor_available": performance_monitor is not None,
            "system_monitor_available": system_monitor is not None,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        logger.error(f"Monitoring health check failed: {e}")
        raise HTTPException(status_code=500, detail="Monitoring health check failed") 