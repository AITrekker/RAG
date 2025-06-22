"""
Health check and system status endpoints for the Enterprise RAG Platform.

Provides endpoints for monitoring system health, dependencies, and performance.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import logging
import time
import psutil
import torch
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()

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


@router.get("/health", response_model=HealthStatus)
async def basic_health_check():
    """
    Basic health check endpoint.
    
    Returns simple health status for load balancers and monitoring systems.
    """
    global request_count, last_minute_requests
    
    request_count += 1
    last_minute_requests.append(time.time())
    
    return HealthStatus(
        status="healthy",
        uptime_seconds=get_uptime()
    )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check():
    """
    Detailed health check endpoint.
    
    Returns comprehensive health status including all system components.
    """
    import asyncio
    
    # Check all components in parallel
    component_checks = await asyncio.gather(
        check_database_health(),
        check_vector_store_health(),
        check_embedding_service_health(),
        return_exceptions=True
    )
    
    components = {}
    overall_status = "healthy"
    
    for check_result in component_checks:
        if isinstance(check_result, ComponentStatus):
            components[check_result.name] = check_result
            if check_result.status != "healthy":
                overall_status = "degraded" if overall_status == "healthy" else "unhealthy"
        else:
            # Handle exceptions
            logger.error(f"Component health check failed: {check_result}")
            overall_status = "unhealthy"
    
    return DetailedHealthResponse(
        status=overall_status,
        uptime_seconds=get_uptime(),
        components=components
    )


@router.get("/status", response_model=SystemStatusResponse)
async def system_status():
    """
    Comprehensive system status endpoint.
    
    Returns detailed system health, metrics, and configuration information.
    """
    # Get detailed health check
    health = await detailed_health_check()
    
    # Get system metrics
    metrics = get_system_metrics()
    
    # System configuration summary
    configuration = {
        "debug_mode": False,  # TODO: Get from settings
        "api_version": "1.0.0",
        "python_version": "3.11",
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "max_request_size": "10MB",
        "rate_limit_per_hour": 1000
    }
    
    return SystemStatusResponse(
        health=health,
        metrics=metrics,
        configuration=configuration
    )


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