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
from src.backend.utils.vector_store import get_vector_store_manager, VectorStoreManager
from src.backend.utils.monitoring import SystemMonitor

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

async def check_vector_store_health(vsm: VectorStoreManager = Depends(get_vector_store_manager)) -> ComponentStatus:
    """Checks the health of the Qdrant vector store."""
    try:
        await asyncio.to_thread(vsm.client.health_check)
        return ComponentStatus(name="vector_store", status="healthy", details={"message": "Qdrant is reachable"})
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

# --- API Endpoints ---

@router.get("/", summary="Comprehensive Health Check", response_model=ComprehensiveHealthResponse)
async def comprehensive_health_check(
    vector_store_status: ComponentStatus = Depends(check_vector_store_health),
    embedding_service_status: ComponentStatus = Depends(check_embedding_service_health),
    llm_service_status: ComponentStatus = Depends(check_llm_service_health),
    monitoring_status: ComponentStatus = Depends(check_monitoring_health)
):
    """
    Comprehensive health check for the entire system.
    
    Checks all critical components:
    - Vector store (Qdrant)
    - Embedding service
    - LLM service
    - Monitoring system
    
    Returns overall system status and detailed component information.
    """
    components = [
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