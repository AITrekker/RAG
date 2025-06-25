"""
RAG query processing API endpoints.

This module provides per-tenant endpoints for:
- Single query processing
- Batch query processing
- Query history and feedback
- Query configuration

All endpoints are scoped to the authenticated tenant.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import datetime
import time

from ...models.api_models import (
    QueryRequest,
    QueryResponse,
    QueryBatchRequest,
    QueryBatchResponse,
    QueryHistoryResponse,
    QueryFeedbackRequest,
    QueryFeedbackResponse,
    SourceCitation,
    ErrorResponse
)
from ...core.rag_pipeline import RAGPipeline
from ...core.llm_service import LLMService
from ...core.embedding_manager import EmbeddingManager
from ...middleware.auth import get_current_tenant
from ...config.settings import get_settings

router = APIRouter(prefix="/query", tags=["RAG Query Processing"])

# =============================================================================
# QUERY PROCESSING
# =============================================================================

@router.post("/ask", response_model=QueryResponse)
async def process_query(
    request: QueryRequest,
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Process a single RAG query.
    
    Args:
        request: Query request with parameters
        current_tenant: Current tenant (from auth)
        
    Returns:
        QueryResponse: Generated answer with sources
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        start_time = time.time()
        
        # Initialize RAG pipeline
        rag_pipeline = RAGPipeline(tenant_id=tenant_id)
        
        # Process query
        result = await rag_pipeline.process_query(
            query=request.query,
            max_sources=request.max_sources,
            confidence_threshold=request.confidence_threshold
        )
        
        processing_time = time.time() - start_time
        
        # Convert sources to citations
        sources = []
        for source in result.sources:
            citation = SourceCitation(
                id=source.id,
                text=source.text,
                score=source.score,
                document_id=source.document_id,
                document_name=source.document_name,
                page_number=source.page_number,
                chunk_index=source.chunk_index
            )
            sources.append(citation)
        
        return QueryResponse(
            query=request.query,
            answer=result.answer,
            sources=sources,
            confidence=result.confidence,
            processing_time=processing_time,
            tokens_used=result.tokens_used,
            model_used=result.model_used
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}"
        )

@router.post("/batch", response_model=QueryBatchResponse)
async def process_batch_queries(
    request: QueryBatchRequest,
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Process multiple queries in batch.
    
    Args:
        request: Batch query request
        current_tenant: Current tenant (from auth)
        
    Returns:
        QueryBatchResponse: Results for all queries
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        start_time = time.time()
        
        # Initialize RAG pipeline
        rag_pipeline = RAGPipeline(tenant_id=tenant_id)
        
        # Process batch queries
        results = []
        successful_queries = 0
        failed_queries = 0
        
        for query_text in request.queries:
            try:
                result = await rag_pipeline.process_query(
                    query=query_text,
                    max_sources=request.max_sources,
                    confidence_threshold=request.confidence_threshold
                )
                
                # Convert sources to citations
                sources = []
                for source in result.sources:
                    citation = SourceCitation(
                        id=source.id,
                        text=source.text,
                        score=source.score,
                        document_id=source.document_id,
                        document_name=source.document_name,
                        page_number=source.page_number,
                        chunk_index=source.chunk_index
                    )
                    sources.append(citation)
                
                query_response = QueryResponse(
                    query=query_text,
                    answer=result.answer,
                    sources=sources,
                    confidence=result.confidence,
                    processing_time=result.processing_time,
                    tokens_used=result.tokens_used,
                    model_used=result.model_used
                )
                
                results.append(query_response)
                successful_queries += 1
                
            except Exception as e:
                # Create error response for failed query
                error_response = QueryResponse(
                    query=query_text,
                    answer=f"Error processing query: {str(e)}",
                    sources=[],
                    confidence=0.0,
                    processing_time=0.0,
                    tokens_used=0,
                    model_used="error"
                )
                results.append(error_response)
                failed_queries += 1
        
        total_processing_time = time.time() - start_time
        
        return QueryBatchResponse(
            results=results,
            total_processing_time=total_processing_time,
            successful_queries=successful_queries,
            failed_queries=failed_queries
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process batch queries: {str(e)}"
        )

# =============================================================================
# QUERY HISTORY
# =============================================================================

@router.get("/history", response_model=QueryHistoryResponse)
async def get_query_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Get query history for the current tenant.
    
    Args:
        page: Page number for pagination
        page_size: Number of queries per page
        current_tenant: Current tenant (from auth)
        
    Returns:
        QueryHistoryResponse: Query history with pagination
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Get query history from RAG pipeline
        rag_pipeline = RAGPipeline(tenant_id=tenant_id)
        history = await rag_pipeline.get_query_history(page=page, page_size=page_size)
        
        return QueryHistoryResponse(
            queries=history,
            total_count=len(history)  # This should be total count, not page count
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get query history: {str(e)}"
        )

@router.post("/feedback", response_model=QueryFeedbackResponse)
async def submit_query_feedback(
    request: QueryFeedbackRequest,
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Submit feedback for a query response.
    
    Args:
        request: Query feedback details
        current_tenant: Current tenant (from auth)
        
    Returns:
        QueryFeedbackResponse: Feedback submission result
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Submit feedback to RAG pipeline
        rag_pipeline = RAGPipeline(tenant_id=tenant_id)
        success = await rag_pipeline.submit_feedback(
            query_id=request.query_id,
            rating=request.rating,
            feedback=request.feedback,
            helpful=request.helpful
        )
        
        if success:
            return QueryFeedbackResponse(
                success=True,
                message="Feedback submitted successfully"
            )
        else:
            return QueryFeedbackResponse(
                success=False,
                message="Failed to submit feedback"
            )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit feedback: {str(e)}"
        )

# =============================================================================
# QUERY CONFIGURATION
# =============================================================================

@router.get("/config")
async def get_query_config(
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Get query configuration for the current tenant.
    
    Args:
        current_tenant: Current tenant (from auth)
        
    Returns:
        dict: Query configuration
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Get query configuration from RAG pipeline
        rag_pipeline = RAGPipeline(tenant_id=tenant_id)
        config = await rag_pipeline.get_query_config()
        
        return config
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get query config: {str(e)}"
        )

@router.put("/config")
async def update_query_config(
    config: dict,
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Update query configuration for the current tenant.
    
    Args:
        config: New query configuration
        current_tenant: Current tenant (from auth)
        
    Returns:
        dict: Updated query configuration
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Update query configuration
        rag_pipeline = RAGPipeline(tenant_id=tenant_id)
        updated_config = await rag_pipeline.update_query_config(config)
        
        return updated_config
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update query config: {str(e)}"
        )

# =============================================================================
# QUERY STATISTICS
# =============================================================================

@router.get("/stats")
async def get_query_stats(
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Get query statistics for the current tenant.
    
    Args:
        current_tenant: Current tenant (from auth)
        
    Returns:
        dict: Query statistics
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Get query statistics from RAG pipeline
        rag_pipeline = RAGPipeline(tenant_id=tenant_id)
        stats = await rag_pipeline.get_query_stats()
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get query stats: {str(e)}"
        )

# =============================================================================
# QUERY VALIDATION
# =============================================================================

@router.post("/validate")
async def validate_query(
    query: str,
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Validate a query without processing it.
    
    Args:
        query: Query text to validate
        current_tenant: Current tenant (from auth)
        
    Returns:
        dict: Validation result
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Validate query
        rag_pipeline = RAGPipeline(tenant_id=tenant_id)
        validation_result = await rag_pipeline.validate_query(query)
        
        return validation_result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate query: {str(e)}"
        ) 