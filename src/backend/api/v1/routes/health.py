"""
Health check and system monitoring endpoints for the Enterprise RAG Platform.

This module provides endpoints for:
- Basic liveness and readiness checks.
- Detailed health checks of individual components (Vector Store, Embedding Service).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging
import asyncio
from datetime import datetime, timezone

from src.backend.core.embedding_manager import get_embedding_manager, EmbeddingManager
from src.backend.utils.vector_store import get_vector_store_manager, VectorStoreManager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

# --- Response Models ---

class ComponentStatus(BaseModel):
    """Health status of an individual component."""
    name: str = Field(..., description="Component name")
    status: str = Field(..., description="Component status ('healthy' or 'unhealthy')")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional component details")

class DetailedHealthResponse(BaseModel):
    """Detailed health check response with component status."""
    overall_status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    components: List[ComponentStatus] = Field(..., description="List of component health statuses")

# --- Health Check Logic ---

async def check_vector_store_health(vsm: VectorStoreManager = Depends(get_vector_store_manager)) -> ComponentStatus:
    """Checks the health of the Qdrant vector store."""
    try:
        # The Qdrant client's `health_check` is a synchronous call.
        # We run it in a thread pool to avoid blocking the event loop.
        await asyncio.to_thread(vsm.client.health_check)
        return ComponentStatus(name="vector_store", status="healthy", details={"message": "Qdrant is reachable."})
    except Exception as e:
        logger.error(f"Vector store health check failed: {e}", exc_info=True)
        return ComponentStatus(name="vector_store", status="unhealthy", details={"error": str(e)})

async def check_embedding_service_health(embed_manager: EmbeddingManager = Depends(get_embedding_manager)) -> ComponentStatus:
    """Checks if the embedding service can generate embeddings."""
    try:
        # Embed a simple test query.
        result = await embed_manager.embed_documents(["health check"])
        if not result or not result[0]:
            raise RuntimeError("Embedding service returned an empty result.")
        return ComponentStatus(name="embedding_service", status="healthy", details={"embedding_dimension": len(result[0])})
    except Exception as e:
        logger.error(f"Embedding service health check failed: {e}", exc_info=True)
        return ComponentStatus(name="embedding_service", status="unhealthy", details={"error": str(e)})

# --- API Endpoints ---

@router.get("/liveness", summary="Basic Liveness Check", response_model=Dict[str, str])
async def liveness_check():
    """
    Confirms the API is running and can respond to requests.
    Does not check dependencies.
    """
    return {"status": "alive"}

@router.get("/readiness", summary="Detailed Readiness Check", response_model=DetailedHealthResponse)
async def readiness_check(
    vector_store_status: ComponentStatus = Depends(check_vector_store_health),
    embedding_service_status: ComponentStatus = Depends(check_embedding_service_health)
):
    """
    Checks the health of the API and its critical dependencies (Qdrant, Embedding Model).
    """
    components = [vector_store_status, embedding_service_status]
    
    is_healthy = all(comp.status == "healthy" for comp in components)
    overall_status = "healthy" if is_healthy else "unhealthy"
    
    return DetailedHealthResponse(
        overall_status=overall_status,
        timestamp=datetime.now(timezone.utc),
        components=components
    )