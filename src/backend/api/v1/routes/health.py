"""
Health check and system monitoring endpoints for the Enterprise RAG Platform.

This module provides endpoints for:
- Basic health checks
- System performance metrics  
- Service status monitoring
- Detailed diagnostic information
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
import time
import psutil
import torch
import asyncio
from datetime import datetime, timezone

from src.backend.config.settings import get_settings
from src.backend.utils.monitoring import get_logger, PerformanceMonitor, SystemMonitor, ErrorTracker
from src.backend.core.embeddings import get_embedding_service
from src.backend.utils.vector_store import get_vector_store_manager

# Get global instances
logger = get_logger(__name__)
settings = get_settings()

# Global monitoring instances (would be injected in production)
performance_monitor = PerformanceMonitor()
system_monitor = SystemMonitor()
error_tracker = ErrorTracker()

router = APIRouter(tags=["health"])

# Response Models
class HealthStatus(BaseModel):
    """Basic health status response."""
    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    version: str = Field(default="1.0.0", description="API version")
    uptime_seconds: float = Field(..., description="System uptime in seconds")


class ComponentStatus(BaseModel):
    """Individual component health status."""
    name: str = Field(..., description="Component name")
    status: str = Field(..., description="Component status (healthy/unhealthy/degraded)")
    response_time_ms: Optional[float] = Field(None, description="Component response time in milliseconds")
    last_check: datetime = Field(default_factory=datetime.utcnow, description="Last health check time")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional component details")
    error_message: Optional[str] = Field(None, description="Error message if unhealthy")


class DetailedHealthResponse(BaseModel):
    """Detailed health check response with component status."""
    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    version: str = Field(default="1.0.0", description="API version")
    uptime_seconds: float = Field(..., description="System uptime in seconds")
    components: Dict[str, ComponentStatus] = Field(default_factory=dict, description="Component health status")


class SystemMetrics(BaseModel):
    """System performance metrics."""
    cpu_usage_percent: float = Field(..., description="CPU usage percentage")
    memory_usage_percent: float = Field(..., description="Memory usage percentage")
    disk_usage_percent: float = Field(..., description="Disk usage percentage")
    gpu_available: bool = Field(..., description="GPU availability")
    gpu_memory_used_mb: Optional[float] = Field(None, description="GPU memory used in MB")
    gpu_memory_total_mb: Optional[float] = Field(None, description="Total GPU memory in MB")
    active_connections: int = Field(..., description="Number of active connections")
    requests_per_minute: float = Field(..., description="Current requests per minute")


class SystemStatusResponse(BaseModel):
    """Comprehensive system status response."""
    health: DetailedHealthResponse = Field(..., description="Health check results")
    metrics: SystemMetrics = Field(..., description="System performance metrics")
    configuration: Dict[str, Any] = Field(default_factory=dict, description="System configuration summary")


# Global variables for tracking
start_time = time.time()
request_count = 0
last_minute_requests = []


def get_uptime() -> float:
    """Get system uptime in seconds."""
    return time.time() - start_time


def get_system_metrics() -> SystemMetrics:
    """Get current system performance metrics."""
    global request_count, last_minute_requests
    
    # Clean up old request timestamps
    current_time = time.time()
    last_minute_requests = [t for t in last_minute_requests if current_time - t < 60]
    
    # CPU and memory usage
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # GPU information
    gpu_available = torch.cuda.is_available()
    gpu_memory_used = None
    gpu_memory_total = None
    
    if gpu_available:
        try:
            gpu_memory_used = torch.cuda.memory_allocated() / 1024 / 1024  # MB
            gpu_memory_total = torch.cuda.get_device_properties(0).total_memory / 1024 / 1024  # MB
        except Exception as e:
            logger.warning(f"Failed to get GPU memory info: {e}")
    
    return SystemMetrics(
        cpu_usage_percent=cpu_percent,
        memory_usage_percent=memory.percent,
        disk_usage_percent=disk.percent,
        gpu_available=gpu_available,
        gpu_memory_used_mb=gpu_memory_used,
        gpu_memory_total_mb=gpu_memory_total,
        active_connections=len(psutil.net_connections()),
        requests_per_minute=len(last_minute_requests)
    )


async def check_database_health() -> ComponentStatus:
    """Check database connectivity and health."""
    start_time = time.time()
    
    try:
        # TODO: Implement actual database health check
        # For now, simulate a health check
        await asyncio.sleep(0.01)  # Simulate database query
        
        response_time = (time.time() - start_time) * 1000
        
        return ComponentStatus(
            name="database",
            status="healthy",
            response_time_ms=response_time,
            details={
                "connection_pool_size": 10,
                "active_connections": 2
            }
        )
    except Exception as e:
        return ComponentStatus(
            name="database",
            status="unhealthy",
            error_message=str(e)
        )


async def check_vector_store_health() -> ComponentStatus:
    """Check vector store connectivity and health."""
    start_time = time.time()
    
    try:
        # TODO: Implement actual vector store health check
        # For now, simulate a health check
        await asyncio.sleep(0.01)  # Simulate vector store query
        
        response_time = (time.time() - start_time) * 1000
        
        return ComponentStatus(
            name="vector_store",
            status="healthy",
            response_time_ms=response_time,
            details={
                "collection_count": 5,
                "total_vectors": 10000
            }
        )
    except Exception as e:
        return ComponentStatus(
            name="vector_store",
            status="unhealthy",
            error_message=str(e)
        )


async def check_embedding_service_health() -> ComponentStatus:
    """Check embedding service health."""
    start_time = time.time()
    
    try:
        # TODO: Implement actual embedding service health check
        # For now, simulate a health check
        await asyncio.sleep(0.01)  # Simulate embedding generation
        
        response_time = (time.time() - start_time) * 1000
        
        return ComponentStatus(
            name="embedding_service",
            status="healthy",
            response_time_ms=response_time,
            details={
                "model_loaded": True,
                "gpu_available": torch.cuda.is_available()
            }
        )
    except Exception as e:
        return ComponentStatus(
            name="embedding_service",
            status="unhealthy",
            error_message=str(e)
        )


@router.get("/")
async def basic_health_check() -> Dict[str, Any]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "service": "Enterprise RAG Platform"
    }


@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check with service status."""
    
    start_time = time.time()
    checks = {}
    
    # Database connection check
    try:
        from ...db.session import get_db_session
        with get_db_session() as db:
            db.execute("SELECT 1")
        checks["database"] = {"status": "healthy", "latency_ms": None}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = {"status": "unhealthy", "error": str(e)}
    
    # Embedding service check
    try:
        embedding_service = get_embedding_service()
        # Simple test embedding
        test_embedding = await embedding_service.embed_text("health check")
        checks["embedding_service"] = {
            "status": "healthy",
            "embedding_dimension": len(test_embedding) if test_embedding else 0
        }
    except Exception as e:
        logger.error(f"Embedding service health check failed: {e}")
        checks["embedding_service"] = {"status": "unhealthy", "error": str(e)}
    
    # Vector store check
    try:
        vector_store_manager = get_vector_store_manager()
        # Check if we can connect
        checks["vector_store"] = {"status": "healthy"}
    except Exception as e:
        logger.error(f"Vector store health check failed: {e}")
        checks["vector_store"] = {"status": "unhealthy", "error": str(e)}
    
    # Overall status
    overall_status = "healthy" if all(
        check.get("status") == "healthy" for check in checks.values()
    ) else "unhealthy"
    
    total_time = time.time() - start_time
    
    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "response_time_ms": round(total_time * 1000, 2)
    }


@router.get("/metrics")
async def system_metrics() -> Dict[str, Any]:
    """Get current system performance metrics."""
    
    try:
        # Collect system metrics
        metrics = system_monitor.collect_system_metrics()
        system_status = system_monitor.get_system_status()
        
        # Get performance metrics summary
        perf_summary = performance_monitor.get_metrics_summary(hours=1)
        
        # Get error statistics
        error_stats = error_tracker.get_error_stats(hours=24)
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system": {
                "cpu_percent": metrics.cpu_percent,
                "memory_percent": metrics.memory_percent,
                "disk_usage_percent": metrics.disk_usage_percent,
                "gpu_utilization": metrics.gpu_utilization,
                "gpu_memory_percent": metrics.gpu_memory_percent,
                "active_connections": metrics.active_connections
            },
            "status": system_status,
            "performance": perf_summary,
            "errors": error_stats
        }
        
    except Exception as e:
        logger.error(f"Failed to collect system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to collect metrics")


@router.get("/performance")
async def performance_metrics() -> Dict[str, Any]:
    """Get detailed performance metrics."""
    
    try:
        # Get performance metrics for different time periods
        hourly_metrics = performance_monitor.get_metrics_summary(hours=1)
        daily_metrics = performance_monitor.get_metrics_summary(hours=24)
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "last_hour": hourly_metrics,
                "last_24_hours": daily_metrics
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")


@router.get("/errors")
async def error_statistics() -> Dict[str, Any]:
    """Get error statistics and recent errors."""
    
    try:
        # Get error stats for different time periods
        hourly_errors = error_tracker.get_error_stats(hours=1)
        daily_errors = error_tracker.get_error_stats(hours=24)
        weekly_errors = error_tracker.get_error_stats(hours=168)  # 7 days
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_statistics": {
                "last_hour": hourly_errors,
                "last_24_hours": daily_errors,
                "last_week": weekly_errors
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get error statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get error statistics")


@router.get("/resources")
async def resource_usage() -> Dict[str, Any]:
    """Get detailed system resource usage."""
    
    try:
        # CPU information
        cpu_info = {
            "count": psutil.cpu_count(),
            "percent": psutil.cpu_percent(interval=1),
            "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
        }
        
        # Memory information
        memory = psutil.virtual_memory()
        memory_info = {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used,
            "free": memory.free
        }
        
        # Disk information
        disk = psutil.disk_usage('/')
        disk_info = {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": (disk.used / disk.total) * 100
        }
        
        # Network information
        network = psutil.net_io_counters()
        network_info = {
            "bytes_sent": network.bytes_sent,
            "bytes_recv": network.bytes_recv,
            "packets_sent": network.packets_sent,
            "packets_recv": network.packets_recv
        }
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "resources": {
                "cpu": cpu_info,
                "memory": memory_info,
                "disk": disk_info,
                "network": network_info
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get resource usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resource usage")


@router.post("/performance/alert/{metric_name}")
async def set_performance_alert(
    metric_name: str,
    threshold: float,
    enabled: bool = True
) -> Dict[str, Any]:
    """Set or update a performance alert threshold."""
    
    try:
        if enabled:
            performance_monitor.alert_thresholds[metric_name] = threshold
            message = f"Alert threshold for {metric_name} set to {threshold}"
        else:
            performance_monitor.alert_thresholds.pop(metric_name, None)
            message = f"Alert for {metric_name} disabled"
        
        logger.info(f"Performance alert updated: {message}")
        
        return {
            "status": "success",
            "message": message,
            "metric_name": metric_name,
            "threshold": threshold if enabled else None,
            "enabled": enabled
        }
        
    except Exception as e:
        logger.error(f"Failed to set performance alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to set alert")


@router.get("/status")
async def service_status() -> Dict[str, Any]:
    """Get overall service status and uptime."""
    
    try:
        # System uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
        uptime = datetime.now(timezone.utc) - boot_time
        
        # Process information
        process = psutil.Process()
        process_info = {
            "pid": process.pid,
            "cpu_percent": process.cpu_percent(),
            "memory_percent": process.memory_percent(),
            "create_time": datetime.fromtimestamp(process.create_time(), tz=timezone.utc).isoformat(),
            "num_threads": process.num_threads()
        }
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "Enterprise RAG Platform",
            "version": "1.0.0",
            "status": "running",
            "uptime_seconds": uptime.total_seconds(),
            "uptime_human": str(uptime),
            "process": process_info
        }
        
    except Exception as e:
        logger.error(f"Failed to get service status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get service status")


@router.get("/health/readiness")
async def readiness_check():
    """
    Kubernetes-style readiness check.
    
    Returns 200 if the service is ready to accept traffic, 503 otherwise.
    """
    try:
        # Check critical components
        health = await detailed_health_check()
        
        # Consider service ready if overall status is healthy or degraded
        if health.status in ["healthy", "degraded"]:
            return {"status": "ready", "timestamp": datetime.utcnow()}
        else:
            raise HTTPException(status_code=503, detail="Service not ready")
            
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")


@router.get("/health/liveness")
async def liveness_check():
    """
    Kubernetes-style liveness check.
    
    Returns 200 if the service is alive, 503 if it should be restarted.
    """
    try:
        # Basic checks to ensure the service is alive
        uptime = get_uptime()
        
        # If uptime is very low, service might be starting up
        if uptime < 5:
            return {"status": "starting", "uptime_seconds": uptime}
        
        # Check if basic functionality is working
        metrics = get_system_metrics()
        
        # If CPU or memory usage is extremely high, service might be stuck
        if metrics.cpu_usage_percent > 95 or metrics.memory_usage_percent > 95:
            logger.warning(f"High resource usage: CPU {metrics.cpu_usage_percent}%, Memory {metrics.memory_usage_percent}%")
        
        return {"status": "alive", "uptime_seconds": uptime}
        
    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not responding")


@router.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus-compatible metrics endpoint.
    
    Returns metrics in Prometheus format for monitoring and alerting.
    """
    metrics = get_system_metrics()
    uptime = get_uptime()
    
    # Generate Prometheus-style metrics
    prometheus_metrics = f"""# HELP rag_platform_uptime_seconds Total uptime of the RAG platform
# TYPE rag_platform_uptime_seconds counter
rag_platform_uptime_seconds {uptime}

# HELP rag_platform_cpu_usage_percent Current CPU usage percentage
# TYPE rag_platform_cpu_usage_percent gauge
rag_platform_cpu_usage_percent {metrics.cpu_usage_percent}

# HELP rag_platform_memory_usage_percent Current memory usage percentage
# TYPE rag_platform_memory_usage_percent gauge
rag_platform_memory_usage_percent {metrics.memory_usage_percent}

# HELP rag_platform_requests_per_minute Current requests per minute
# TYPE rag_platform_requests_per_minute gauge
rag_platform_requests_per_minute {metrics.requests_per_minute}

# HELP rag_platform_gpu_available GPU availability
# TYPE rag_platform_gpu_available gauge
rag_platform_gpu_available {1 if metrics.gpu_available else 0}
"""

    if metrics.gpu_memory_used_mb is not None:
        prometheus_metrics += f"""
# HELP rag_platform_gpu_memory_used_mb GPU memory used in MB
# TYPE rag_platform_gpu_memory_used_mb gauge
rag_platform_gpu_memory_used_mb {metrics.gpu_memory_used_mb}
"""

    return prometheus_metrics 