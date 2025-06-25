"""
LLM Service API Routes

This module provides API endpoints for LLM text generation,
model management, and performance monitoring.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
import logging

from src.backend.core.llm_service import (
    get_llm_service,
    get_model_recommendations,
    generate_answer,
    generate_rag_answer,
    get_llm_stats
)
from src.backend.models.api_models import (
    LLMGenerateRequest,
    LLMGenerateResponse,
    LLMServiceInfo,
    LLMStatsResponse
)
from src.backend.middleware.auth import get_current_tenant_id

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/info", response_model=LLMServiceInfo)
async def get_llm_service_info():
    """Get information about the LLM service configuration."""
    try:
        llm_service = get_llm_service()
        
        return LLMServiceInfo(
            model_name=llm_service.model_name,
            max_length=llm_service.max_length,
            temperature=llm_service.temperature,
            device=llm_service.device,
            is_loaded=llm_service.model is not None,
            quantization_enabled=llm_service.enable_quantization
        )
    except Exception as e:
        logger.error(f"Failed to get LLM service info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get LLM service info")


@router.post("/generate", response_model=LLMGenerateResponse)
async def generate_text(
    request: LLMGenerateRequest,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """Generate text using the LLM service."""
    try:
        llm_service = get_llm_service()
        
        # Prepare context if provided
        context = None
        if request.context:
            context = request.context
        
        # Generate response
        response = llm_service.generate_response(
            prompt=request.prompt,
            context=context,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature,
            do_sample=request.do_sample,
            top_p=request.top_p,
            top_k=request.top_k,
            repetition_penalty=request.repetition_penalty
        )
        
        if not response.success:
            raise HTTPException(status_code=500, detail=response.error)
        
        return LLMGenerateResponse(
            text=response.text,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
            generation_time=response.generation_time,
            model_name=response.model_name,
            temperature=response.temperature
        )
    except Exception as e:
        logger.error(f"Failed to generate text: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate text")


@router.get("/models")
async def get_available_models():
    """Get information about available LLM models."""
    try:
        models = get_model_recommendations()
        
        return {
            "models": models,
            "total_models": len(models)
        }
    except Exception as e:
        logger.error(f"Failed to get available models: {e}")
        raise HTTPException(status_code=500, detail="Failed to get available models")


@router.get("/stats", response_model=LLMStatsResponse)
async def get_llm_statistics():
    """Get LLM service statistics and performance metrics."""
    try:
        stats = get_llm_stats()
        llm_service = get_llm_service()
        
        return LLMStatsResponse(
            generation_times=stats.get("generation_times", []),
            total_tokens_generated=stats.get("total_tokens_generated", 0),
            average_generation_time=stats.get("average_generation_time", 0.0),
            model_name=llm_service.model_name,
            device=llm_service.device
        )
    except Exception as e:
        logger.error(f"Failed to get LLM stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get LLM statistics")


@router.post("/clear-cache")
async def clear_llm_cache():
    """Clear the LLM service cache."""
    try:
        llm_service = get_llm_service()
        llm_service.clear_cache()
        
        return {"message": "LLM cache cleared successfully"}
    except Exception as e:
        logger.error(f"Failed to clear LLM cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear LLM cache")


@router.post("/clear-stats")
async def clear_llm_statistics():
    """Clear LLM service statistics."""
    try:
        llm_service = get_llm_service()
        llm_service.clear_stats()
        
        return {"message": "LLM statistics cleared successfully"}
    except Exception as e:
        logger.error(f"Failed to clear LLM stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear LLM statistics") 