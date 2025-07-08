"""
RAG Query API Routes - Using the new service architecture
"""

import time
from fastapi import APIRouter, HTTPException, Depends, status, Query, Request
from typing import List, Optional, Dict, Any
from uuid import UUID

from src.backend.dependencies import (
    get_current_tenant_dep,
    get_rag_service_dep,
    get_db
)
from src.backend.services.rag_service import RAGService
from src.backend.services.analytics_service import AnalyticsService
from src.backend.models.database import Tenant
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/")
async def process_query(
    request_data: Dict[str, Any],
    request: Request,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    rag_service: RAGService = Depends(get_rag_service_dep),
    db: Session = Depends(get_db)
):
    """Process a RAG query with comprehensive analytics tracking"""
    start_time = time.time()
    analytics = AnalyticsService(db)
    query_log = None
    
    try:
        query = request_data.get("query", "").strip()
        if not query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query cannot be empty"
            )
        
        max_sources = request_data.get("max_sources", 5)
        confidence_threshold = request_data.get("confidence_threshold", 0.7)
        metadata_filters = request_data.get("metadata_filters")
        
        # Get request context for analytics
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        session_id = request.headers.get("x-session-id")
        
        # Process the query
        response = await rag_service.process_query(
            query=query,
            tenant_id=current_tenant.id,
            max_sources=max_sources,
            confidence_threshold=confidence_threshold,
            metadata_filters=metadata_filters
        )
        
        # Calculate response time
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        
        # Determine response type
        response_type = "success"
        if not response.answer or response.answer.lower().strip() in ["no answer", "no information found", ""]:
            response_type = "no_answer"
        elif response.confidence and response.confidence < confidence_threshold:
            response_type = "low_confidence"
        
        # Log the query
        query_log = analytics.log_query(
            tenant_id=current_tenant.id,
            query_text=query,
            response_text=response.answer,
            response_type=response_type,
            response_time_ms=response_time_ms,
            confidence_score=response.confidence,
            sources_count=len(response.sources),
            chunks_retrieved=len(response.sources),
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            embedding_model=response.embedding_model if hasattr(response, 'embedding_model') else 'all-MiniLM-L6-v2',
            llm_model=response.model_used,
            tokens_used=response.tokens_used,
            embedding_time_ms=response.embedding_time if hasattr(response, 'embedding_time') else None,
            search_time_ms=response.search_time if hasattr(response, 'search_time') else None,
            llm_time_ms=response.llm_time if hasattr(response, 'llm_time') else None
        )
        
        # Log document access for each source
        for idx, source in enumerate(response.sources):
            analytics.log_document_access(
                query_log_id=query_log.id,
                file_id=source.file_id,
                tenant_id=current_tenant.id,
                relevance_score=source.score,
                rank_position=idx + 1,
                chunks_used=1,
                included_in_response=True
            )
        
        # Update session activity if session_id provided
        if session_id:
            analytics.update_session_activity(session_id, query_count_increment=1)
        
        # Commit analytics data
        analytics.commit()
        
        return {
            "query": response.query,
            "answer": response.answer,
            "sources": [
                {
                    "chunk_id": str(source.chunk_id),
                    "file_id": str(source.file_id),
                    "content": source.content,
                    "score": source.score,
                    "metadata": source.metadata,
                    "chunk_index": source.chunk_index,
                    "filename": source.filename
                }
                for source in response.sources
            ],
            "confidence": response.confidence,
            "processing_time": response.processing_time,
            "model_used": response.model_used,
            "tokens_used": response.tokens_used,
            "query_id": str(query_log.id) if query_log else None,
            "response_type": response_type
        }
        
    except HTTPException:
        # Log failed query if we got far enough to create a log entry
        if query_log:
            end_time = time.time()
            response_time_ms = int((end_time - start_time) * 1000)
            query_log.response_type = "error"
            query_log.response_time_ms = response_time_ms
            analytics.commit()
        raise
    except Exception as e:
        # Log error query
        try:
            end_time = time.time()
            response_time_ms = int((end_time - start_time) * 1000)
            
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            session_id = request.headers.get("x-session-id")
            
            analytics.log_query(
                tenant_id=current_tenant.id,
                query_text=request_data.get("query", ""),
                response_text=None,
                response_type="error",
                response_time_ms=response_time_ms,
                confidence_score=None,
                sources_count=0,
                chunks_retrieved=0,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            analytics.commit()
        except:
            pass  # Don't let analytics errors mask the original error
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )


@router.post("/batch")
async def process_batch_queries(
    request: Dict[str, Any],
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    rag_service: RAGService = Depends(get_rag_service_dep)
):
    """Process multiple queries in batch - NOT IMPLEMENTED"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Batch query processing not yet implemented",
            "planned_features": [
                "Parallel query processing",
                "Batch response with success/failure counts",
                "Optimized resource usage"
            ],
            "status": "planned"
        }
    )


@router.post("/search")
async def semantic_search(
    request: Dict[str, Any],
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    rag_service: RAGService = Depends(get_rag_service_dep)
):
    """Perform semantic search without answer generation"""
    try:
        query = request.get("query", "").strip()
        if not query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query cannot be empty"
            )
        
        max_results = request.get("max_results", 20)
        metadata_filters = request.get("metadata_filters")
        
        results = await rag_service.semantic_search(
            query=query,
            tenant_id=current_tenant.id,
            max_results=max_results,
            metadata_filters=metadata_filters
        )
        
        return {
            "query": query,
            "results": [
                {
                    "chunk_id": str(result.chunk_id),
                    "file_id": str(result.file_id),
                    "content": result.content,
                    "score": result.score,
                    "metadata": result.metadata,
                    "chunk_index": result.chunk_index,
                    "filename": result.filename
                }
                for result in results
            ],
            "total_results": len(results)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform search: {str(e)}"
        )


@router.get("/documents")
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search_query: Optional[str] = Query(None),
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    rag_service: RAGService = Depends(get_rag_service_dep)
):
    """List documents with optional search"""
    try:
        result = await rag_service.get_tenant_documents(
            tenant_id=current_tenant.id,
            page=page,
            page_size=page_size,
            search_query=search_query
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents: {str(e)}"
        )


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    rag_service: RAGService = Depends(get_rag_service_dep)
):
    """Get specific document details - NOT IMPLEMENTED"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Document detail retrieval not yet implemented",
            "planned_features": [
                "Document metadata retrieval",
                "Chunk information",
                "Processing status"
            ],
            "status": "planned"
        }
    )


@router.get("/history")
async def get_query_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    rag_service: RAGService = Depends(get_rag_service_dep)
):
    """Get query history - NOT IMPLEMENTED"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Query history not yet implemented",
            "planned_features": [
                "Query history with pagination",
                "Search and filtering",
                "Export capabilities"
            ],
            "status": "planned"
        }
    )


@router.post("/validate")
async def validate_query(
    request: Dict[str, Any],
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    rag_service: RAGService = Depends(get_rag_service_dep)
):
    """Validate a query without processing it"""
    try:
        query = request.get("query", "")
        
        validation = await rag_service.validate_query(query, current_tenant.id)
        
        return validation
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate query: {str(e)}"
        )


@router.get("/suggestions")
async def get_query_suggestions(
    partial_query: str = Query(..., min_length=1),
    max_suggestions: int = Query(5, ge=1, le=10),
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    rag_service: RAGService = Depends(get_rag_service_dep)
):
    """Get query suggestions - STUBBED"""
    # This is stubbed in the RAG service, so we'll return a proper stub response
    return {
        "suggestions": [
            f"{partial_query} example 1",
            f"{partial_query} example 2", 
            f"{partial_query} example 3"
        ],
        "status": "stubbed",
        "message": "Query suggestions are stubbed - real implementation planned"
    }


@router.get("/stats")
async def get_query_stats(
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    rag_service: RAGService = Depends(get_rag_service_dep)
):
    """Get RAG usage statistics - STUBBED"""
    # This is stubbed in the RAG service, so we'll return a proper stub response
    return {
        "tenant_id": str(current_tenant.id),
        "total_queries": 0,
        "successful_queries": 0,
        "failed_queries": 0,
        "average_processing_time": 0.0,
        "average_confidence": 0.0,
        "most_common_queries": [],
        "query_trends": {},
        "feedback_stats": {},
        "status": "stubbed",
        "message": "Query statistics are stubbed - real implementation planned"
    }


@router.post("/feedback")
async def submit_feedback(
    request: Dict[str, Any],
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    rag_service: RAGService = Depends(get_rag_service_dep)
):
    """Submit query feedback - STUBBED"""
    # This is stubbed in the RAG service, so we'll return a proper stub response
    query_id = request.get("query_id")
    rating = request.get("rating")
    feedback = request.get("feedback")
    helpful = request.get("helpful")
    
    if not query_id or rating is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="query_id and rating are required"
        )
    
    return {
        "success": True,
        "message": "Feedback received (stubbed - not yet stored)",
        "query_id": query_id,
        "rating": rating,
        "feedback": feedback,
        "helpful": helpful,
        "status": "stubbed",
        "note": "Feedback storage not yet implemented"
    }


@router.get("/config")
async def get_query_config(
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    rag_service: RAGService = Depends(get_rag_service_dep)
):
    """Get query configuration - NOT IMPLEMENTED"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Query configuration not yet implemented",
            "planned_features": [
                "Per-tenant query settings",
                "Model configuration",
                "Processing parameters"
            ],
            "status": "planned"
        }
    )


@router.put("/config")
async def update_query_config(
    config: Dict[str, Any],
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    rag_service: RAGService = Depends(get_rag_service_dep)
):
    """Update query configuration - NOT IMPLEMENTED"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Query configuration updates not yet implemented",
            "planned_features": [
                "Configuration validation",
                "Settings persistence",
                "Configuration history"
            ],
            "status": "planned"
        }
    )