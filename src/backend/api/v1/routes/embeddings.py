"""
Embedding Management API Routes

This module provides API endpoints for managing embedding generation,
monitoring embedding performance, and accessing embedding statistics.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
import logging

from src.backend.core.embedding_manager import (
    get_embedding_manager,
    embed_texts_sync,
    embed_texts_async,
    get_pipeline_stats
)
from src.backend.core.embeddings import get_embedding_service
from src.backend.models.api_models import (
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingStatsResponse,
    EmbeddingServiceInfo,
    BatchEmbeddingRequest,
    BatchEmbeddingResponse
)
from src.backend.middleware.auth import get_current_tenant_id

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/info", response_model=EmbeddingServiceInfo)
async def get_embedding_service_info():
    """Get information about the embedding service configuration."""
    try:
        embedding_service = get_embedding_service()
        
        return EmbeddingServiceInfo(
            model_name=embedding_service.model_name,
            model_path=embedding_service.model_path,
            embedding_dimension=embedding_service.embedding_dimension,
            max_sequence_length=embedding_service.max_sequence_length,
            device=embedding_service.device,
            is_loaded=embedding_service.is_loaded,
            supports_normalization=embedding_service.supports_normalization
        )
    except Exception as e:
        logger.error(f"Failed to get embedding service info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get embedding service info")


@router.post("/generate", response_model=EmbeddingResponse)
async def generate_embeddings(
    request: EmbeddingRequest,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """Generate embeddings for a single text."""
    try:
        result = embed_texts_sync(
            texts=[request.text],
            tenant_id=tenant_id,
            metadata=[request.metadata] if request.metadata else None,
            doc_ids=[request.doc_id] if request.doc_id else None
        )
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        
        return EmbeddingResponse(
            embeddings=result.embeddings.tolist(),
            text=request.text,
            metadata=request.metadata,
            doc_id=request.doc_id,
            processing_time=result.processing_time,
            embedding_dimension=result.embeddings.shape[1] if result.embeddings.size > 0 else 0
        )
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate embeddings")


@router.post("/generate-batch", response_model=BatchEmbeddingResponse)
async def generate_batch_embeddings(
    request: BatchEmbeddingRequest,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """Generate embeddings for multiple texts in batch."""
    try:
        result = embed_texts_sync(
            texts=request.texts,
            tenant_id=tenant_id,
            metadata=request.metadata,
            doc_ids=request.doc_ids
        )
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        
        return BatchEmbeddingResponse(
            embeddings=result.embeddings.tolist(),
            texts=result.texts,
            metadata=result.metadata,
            doc_ids=result.doc_ids,
            processing_time=result.processing_time,
            embedding_dimension=result.embeddings.shape[1] if result.embeddings.size > 0 else 0,
            batch_size=len(request.texts)
        )
    except Exception as e:
        logger.error(f"Failed to generate batch embeddings: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate batch embeddings")


@router.post("/generate-async")
async def submit_async_embedding_job(
    request: BatchEmbeddingRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """Submit an asynchronous embedding generation job."""
    try:
        embedding_manager = get_embedding_manager()
        
        # Submit to background queue
        success = embedding_manager.submit_request(
            texts=request.texts,
            metadata=request.metadata,
            doc_ids=request.doc_ids,
            tenant_id=tenant_id,
            priority=request.priority if hasattr(request, 'priority') else 0
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to submit embedding job")
        
        return {
            "message": "Embedding job submitted successfully",
            "job_id": f"embed_{tenant_id}_{len(request.texts)}",
            "texts_count": len(request.texts),
            "tenant_id": tenant_id
        }
    except Exception as e:
        logger.error(f"Failed to submit async embedding job: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit embedding job")


@router.get("/stats", response_model=EmbeddingStatsResponse)
async def get_embedding_stats():
    """Get embedding generation statistics and performance metrics."""
    try:
        embedding_manager = get_embedding_manager()
        pipeline_stats = get_pipeline_stats()
        
        manager_stats = embedding_manager.get_stats()
        
        return EmbeddingStatsResponse(
            processed_requests=manager_stats.get("processed_requests", 0),
            total_texts_processed=manager_stats.get("total_texts_processed", 0),
            total_processing_time=manager_stats.get("total_processing_time", 0.0),
            error_count=manager_stats.get("error_count", 0),
            average_processing_time=manager_stats.get("average_processing_time", 0.0),
            requests_per_second=manager_stats.get("requests_per_second", 0.0),
            worker_threads=manager_stats.get("worker_threads", 0),
            queue_size=manager_stats.get("queue_size", 0),
            pipeline_stats=pipeline_stats
        )
    except Exception as e:
        logger.error(f"Failed to get embedding stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get embedding statistics") 