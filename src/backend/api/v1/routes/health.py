"""
Comprehensive Health Check API Routes

This module provides a unified health check endpoint that checks all system components
including vector store, embedding service, LLM service, and monitoring.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
import asyncio
from datetime import datetime, timezone

from src.backend.core.embedding_manager import get_embedding_manager, EmbeddingManager
from src.backend.core.llm_service import get_llm_service
# DEPRECATED: Vector store functionality moved to PostgreSQL + pgvector
# from src.backend.utils.vector_store import get_vector_store_manager, VectorStoreManager
from src.backend.utils.monitoring import SystemMonitor
from src.backend.database import get_pool_status, check_database_health

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])

# --- Response Models ---

class ComponentStatus(BaseModel):
    """Health status of an individual component."""
    name: str = Field(..., description="Component name")
    status: str = Field(..., description="Component status ('healthy' or 'unhealthy')")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional component details")

class ComprehensiveHealthResponse(BaseModel):
    """Comprehensive health check response with all component statuses."""
    overall_status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    components: List[ComponentStatus] = Field(..., description="List of component health statuses")
    system_metrics: Optional[Dict[str, Any]] = Field(None, description="System resource metrics")

# --- Health Check Logic ---

async def check_vector_store_health() -> ComponentStatus:
    """Checks the health of PostgreSQL + pgvector."""
    try:
        # pgvector is part of PostgreSQL, so if database is healthy, vectors are healthy
        db_healthy = await check_database_health()
        if db_healthy:
            return ComponentStatus(name="vector_store", status="healthy", details={"message": "PostgreSQL + pgvector is operational"})
        else:
            return ComponentStatus(name="vector_store", status="unhealthy", details={"error": "PostgreSQL connection failed"})
    except Exception as e:
        logger.error(f"Vector store health check failed: {e}", exc_info=True)
        return ComponentStatus(name="vector_store", status="unhealthy", details={"error": str(e)})

async def check_embedding_service_health(embed_manager: EmbeddingManager = Depends(get_embedding_manager)) -> ComponentStatus:
    """Checks if the embedding service can generate embeddings."""
    try:
        from src.backend.core.embeddings import get_embedding_service
        embedding_service = get_embedding_service()
        
        # Check if service is loaded
        if not embedding_service.is_loaded:
            return ComponentStatus(
                name="embedding_service", 
                status="unhealthy", 
                details={"error": "Embedding service not loaded"}
            )
        
        # Test embedding generation
        result = embed_manager.process_sync(["health check"], tenant_id="health_check")
        if not result.success:
            return ComponentStatus(
                name="embedding_service", 
                status="unhealthy", 
                details={"error": result.error}
            )
        
        return ComponentStatus(
            name="embedding_service", 
            status="healthy", 
            details={
                "embedding_dimension": result.embeddings.shape[1] if result.embeddings.size > 0 else 0,
                "model_name": embedding_service.model_name,
                "device": embedding_service.device
            }
        )
    except Exception as e:
        logger.error(f"Embedding service health check failed: {e}", exc_info=True)
        return ComponentStatus(name="embedding_service", status="unhealthy", details={"error": str(e)})

async def check_llm_service_health() -> ComponentStatus:
    """Checks if the LLM service is properly loaded and functional."""
    try:
        llm_service = get_llm_service()
        
        # Check if model components are loaded
        is_model_loaded = llm_service.model is not None
        is_tokenizer_loaded = llm_service.tokenizer is not None
        is_pipeline_ready = llm_service.pipeline is not None
        
        if not all([is_model_loaded, is_tokenizer_loaded, is_pipeline_ready]):
            return ComponentStatus(
                name="llm_service",
                status="unhealthy",
                details={
                    "model_loaded": is_model_loaded,
                    "tokenizer_loaded": is_tokenizer_loaded,
                    "pipeline_ready": is_pipeline_ready
                }
            )
        
        return ComponentStatus(
            name="llm_service",
            status="healthy",
            details={
                "model_name": llm_service.model_name,
                "device": llm_service.device,
                "quantization_enabled": llm_service.enable_quantization
            }
        )
    except Exception as e:
        logger.error(f"LLM service health check failed: {e}", exc_info=True)
        return ComponentStatus(name="llm_service", status="unhealthy", details={"error": str(e)})

async def check_monitoring_health() -> ComponentStatus:
    """Checks if the monitoring system is functional."""
    try:
        system_monitor = SystemMonitor()
        metrics = system_monitor.collect_system_metrics()
        
        return ComponentStatus(
            name="monitoring",
            status="healthy",
            details={
                "cpu_percent": metrics.cpu_percent,
                "memory_percent": metrics.memory_percent,
                "disk_usage_percent": metrics.disk_usage_percent
            }
        )
    except Exception as e:
        logger.error(f"Monitoring health check failed: {e}", exc_info=True)
        return ComponentStatus(name="monitoring", status="unhealthy", details={"error": str(e)})

async def check_database_health_status() -> ComponentStatus:
    """Checks database connectivity and connection pool status."""
    try:
        # Check basic database health
        is_db_healthy = await check_database_health()
        
        # Get pool statistics
        pool_stats = get_pool_status()
        
        # Determine if pool is in good state
        utilization = pool_stats["utilization_pct"]
        is_pool_healthy = utilization < 85  # Warning threshold
        
        status = "healthy" if is_db_healthy and is_pool_healthy else "unhealthy"
        
        return ComponentStatus(
            name="database",
            status=status,
            details={
                "db_connectivity": is_db_healthy,
                "pool_utilization_pct": utilization,
                "connections_in_use": pool_stats["checkedout"],
                "connections_checkedin": pool_stats["checkedin"],
                "total_capacity": pool_stats["total_capacity"],
                "pool_size": pool_stats["pool_size"],
                "overflow": pool_stats["overflow"]
            }
        )
    except Exception as e:
        logger.error(f"Database health check failed: {e}", exc_info=True)
        return ComponentStatus(name="database", status="unhealthy", details={"error": str(e)})

# --- API Endpoints ---

@router.get("/", summary="Comprehensive Health Check", response_model=ComprehensiveHealthResponse)
async def comprehensive_health_check(
    vector_store_status: ComponentStatus = Depends(check_vector_store_health),
    embedding_service_status: ComponentStatus = Depends(check_embedding_service_health),
    llm_service_status: ComponentStatus = Depends(check_llm_service_health),
    monitoring_status: ComponentStatus = Depends(check_monitoring_health),
    database_status: ComponentStatus = Depends(check_database_health_status)
):
    """
    Comprehensive health check for the entire system.
    
    Checks all critical components:
    - Vector store (PostgreSQL + pgvector)
    - Embedding service
    - LLM service
    - Monitoring system
    
    Returns overall system status and detailed component information.
    """
    components = [
        database_status,
        vector_store_status,
        embedding_service_status,
        llm_service_status,
        monitoring_status
    ]
    
    # Determine overall status
    is_healthy = all(comp.status == "healthy" for comp in components)
    overall_status = "healthy" if is_healthy else "unhealthy"
    
    # Get system metrics from monitoring component
    system_metrics = None
    if monitoring_status.status == "healthy" and monitoring_status.details:
        system_metrics = monitoring_status.details
    
    return ComprehensiveHealthResponse(
        overall_status=overall_status,
        timestamp=datetime.now(timezone.utc),
        components=components,
        system_metrics=system_metrics
    )

@router.get("/liveness", summary="Basic Liveness Check", response_model=Dict[str, str])
async def liveness_check():
    """
    Basic liveness check - confirms the API is running and can respond to requests.
    Does not check dependencies.
    """
    return {"status": "alive"}

@router.get("/database", summary="Database Connection Pool Status", response_model=Dict[str, Any])
async def database_pool_status():
    """
    Get detailed database connection pool status for monitoring and debugging.
    """
    try:
        pool_stats = get_pool_status()
        is_healthy = await check_database_health()
        
        return {
            "database_healthy": is_healthy,
            "pool_stats": pool_stats,
            "recommendations": [
                "Consider increasing pool size" if pool_stats["utilization_pct"] > 80 else "Pool size is adequate",
                "Pool appears healthy" if pool_stats["checkedout"] < pool_stats["total_capacity"] else "Pool at capacity",
                "Monitor for long-running queries" if pool_stats["checkedout"] > 20 else "Connection usage is normal"
            ]
        }
    except Exception as e:
        return {
            "database_healthy": False,
            "error": str(e),
            "recommendations": ["Check database connectivity", "Restart database service if needed"]
        }