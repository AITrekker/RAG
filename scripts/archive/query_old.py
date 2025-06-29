"""
RAG query processing API endpoints.

This module provides per-tenant endpoints for:
- Single query processing with metadata filtering
- Batch query processing
- Query history and feedback
- Document listing and search
- Query configuration

All endpoints are scoped to the authenticated tenant.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
import time
import logging

from src.backend.models.api_models import (
    QueryRequest,
    QueryResponse,
    QueryBatchRequest,
    QueryBatchResponse,
    QueryHistoryResponse,
    QueryFeedbackRequest,
    QueryFeedbackResponse,
    SourceCitation,
    ErrorResponse,
    DocumentListResponse,
    DocumentResponse
)
from src.backend.core.rag_pipeline import get_rag_pipeline
from src.backend.core.llm_service import LLMService
from src.backend.core.embedding_manager import EmbeddingManager
from src.backend.middleware.api_key_auth import get_current_tenant
from src.backend.config.settings import get_settings
from src.backend.utils.error_handling import (
    RAGPipelineError,
    LLMError,
    EmbeddingError,
    ValidationError as ValidationErrorCustom,
    not_found_error,
    validation_error,
    internal_error
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/queries", tags=["RAG Query Processing"])

# =============================================================================
# QUERY PROCESSING
# =============================================================================

@router.post("/", response_model=QueryResponse)
async def create_query(
    request: QueryRequest,
    current_tenant = Depends(get_current_tenant)
):
    """
    Process a single RAG query with metadata filtering.
    
    Args:
        request: Query request with parameters and metadata filters
        current_tenant: Current tenant (from auth)
        
    Returns:
        QueryResponse: Generated answer with sources and metadata
    """
    try:
        tenant_id = current_tenant.id
        start_time = time.time()
        
        # Validate input
        if not request.query or not request.query.strip():
            raise ValidationErrorCustom("Query cannot be empty")
        
        if request.max_sources < 1 or request.max_sources > 20:
            raise ValidationErrorCustom("max_sources must be between 1 and 20")
        
        if request.confidence_threshold < 0.0 or request.confidence_threshold > 1.0:
            raise ValidationErrorCustom("confidence_threshold must be between 0.0 and 1.0")
        
        # Initialize RAG pipeline
        rag_pipeline = get_rag_pipeline()
        
        # Process query with metadata filtering
        result = await rag_pipeline.process_query_with_metadata(
            query=request.query, 
            tenant_id=tenant_id,
            metadata_filters=request.metadata_filters if hasattr(request, 'metadata_filters') else None,
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
                chunk_index=source.chunk_index,
                metadata=source.metadata if hasattr(source, 'metadata') else None
            )
            sources.append(citation)
        
        return QueryResponse(
            query=request.query,
            answer=result.answer,
            sources=sources,
            confidence=result.confidence,
            processing_time=processing_time,
            tokens_used=result.llm_metadata.get("total_tokens") if result.llm_metadata else None,
            model_used=result.llm_metadata.get("model_name") if result.llm_metadata else None
        )
        
    except ValidationErrorCustom as e:
        logger.warning(f"Validation error in query processing: {e}")
        raise validation_error(str(e))
    except RAGPipelineError as e:
        logger.error(f"RAG pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in query processing: {e}", exc_info=True)
        raise internal_error(f"Failed to process query: {str(e)}")

@router.post("/batch", response_model=QueryBatchResponse)
async def process_batch_queries(
    request: QueryBatchRequest,
    current_tenant = Depends(get_current_tenant)
):
    """
    Process multiple queries in batch with metadata filtering.
    
    Args:
        request: Batch query request with metadata filters
        current_tenant: Current tenant (from auth)
        
    Returns:
        QueryBatchResponse: Results for all queries
    """
    try:
        tenant_id = current_tenant.id
        start_time = time.time()
        
        # Validate input
        if not request.queries or len(request.queries) == 0:
            raise ValidationErrorCustom("At least one query is required")
        
        if len(request.queries) > 10:
            raise ValidationErrorCustom("Maximum 10 queries allowed per batch")
        
        # Initialize RAG pipeline
        rag_pipeline = get_rag_pipeline()
        
        # Process batch queries
        results = []
        successful_queries = 0
        failed_queries = 0
        
        for query_text in request.queries:
            try:
                result = await rag_pipeline.process_query_with_metadata(
                    query=query_text,
                    tenant_id=tenant_id,
                    metadata_filters=request.metadata_filters if hasattr(request, 'metadata_filters') else None,
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
                        chunk_index=source.chunk_index,
                        metadata=source.metadata if hasattr(source, 'metadata') else None
                    )
                    sources.append(citation)
                
                query_response = QueryResponse(
                    query=query_text,
                    answer=result.answer,
                    sources=sources,
                    confidence=result.confidence,
                    processing_time=result.processing_time,
                    tokens_used=result.llm_metadata.get("total_tokens") if result.llm_metadata else None,
                    model_used=result.llm_metadata.get("model_name") if result.llm_metadata else None
                )
                
                results.append(query_response)
                successful_queries += 1
                
            except Exception as e:
                logger.error(f"Error processing query '{query_text}': {e}")
                # Create error response for failed query
                error_response = QueryResponse(
                    query=query_text,
                    answer=f"Error processing query: {str(e)}",
                    sources=[],
                    confidence=0.0,
                    processing_time=0.0
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
        
    except ValidationErrorCustom as e:
        logger.warning(f"Validation error in batch query processing: {e}")
        raise validation_error(str(e))
    except Exception as e:
        logger.error(f"Unexpected error in batch query processing: {e}", exc_info=True)
        raise internal_error(f"Failed to process batch queries: {str(e)}")

# =============================================================================
# DOCUMENT ACCESS
# =============================================================================

@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search in document metadata"),
    author: Optional[str] = Query(None, description="Filter by author"),
    date_from: Optional[str] = Query(None, description="Filter by date from (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter by date to (YYYY-MM-DD)"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    current_tenant = Depends(get_current_tenant)
):
    """
    List documents with metadata filtering and search.
    
    Args:
        page: Page number for pagination
        page_size: Number of documents per page
        search: Search term for metadata
        author: Filter by author
        date_from: Filter by date from
        date_to: Filter by date to
        tags: Filter by tags
        document_type: Filter by document type
        current_tenant: Current tenant (from auth)
        
    Returns:
        DocumentListResponse: List of documents with metadata
    """
    try:
        tenant_id = current_tenant.id
        
        # Build metadata filters
        metadata_filters = {}
        if author:
            metadata_filters["author"] = author
        if date_from:
            metadata_filters["date_from"] = date_from
        if date_to:
            metadata_filters["date_to"] = date_to
        if tags:
            metadata_filters["tags"] = [tag.strip() for tag in tags.split(",")]
        if document_type:
            metadata_filters["document_type"] = document_type
        
        # Get documents from RAG pipeline
        rag_pipeline = get_rag_pipeline()
        documents_result = await rag_pipeline.list_documents_with_metadata(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            search=search,
            metadata_filters=metadata_filters
        )
        
        return DocumentListResponse(
            documents=documents_result.documents,
            total_count=documents_result.total_count,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Failed to list documents: {e}", exc_info=True)
        raise internal_error(f"Failed to list documents: {str(e)}")

@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_tenant = Depends(get_current_tenant)
):
    """
    Get document details with metadata.
    
    Args:
        document_id: Document ID
        current_tenant: Current tenant (from auth)
        
    Returns:
        DocumentResponse: Document details with metadata
    """
    try:
        tenant_id = current_tenant.id
        
        # Get document from RAG pipeline
        rag_pipeline = get_rag_pipeline()
        document = await rag_pipeline.get_document_with_metadata(
            tenant_id=tenant_id,
            document_id=document_id
        )
        
        if not document:
            raise not_found_error("Document", document_id)
        
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {document_id}: {e}", exc_info=True)
        raise internal_error(f"Failed to get document: {str(e)}")

@router.get("/search", response_model=List[DocumentResponse])
async def search_documents(
    query: str = Query(..., min_length=1, description="Search query"),
    max_results: int = Query(20, ge=1, le=100, description="Maximum results"),
    author: Optional[str] = Query(None, description="Filter by author"),
    date_from: Optional[str] = Query(None, description="Filter by date from"),
    date_to: Optional[str] = Query(None, description="Filter by date to"),
    tags: Optional[str] = Query(None, description="Filter by tags"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    current_tenant = Depends(get_current_tenant)
):
    """
    Search documents by content and metadata.
    
    Args:
        query: Search query
        max_results: Maximum number of results
        author: Filter by author
        date_from: Filter by date from
        date_to: Filter by date to
        tags: Filter by tags
        document_type: Filter by document type
        current_tenant: Current tenant (from auth)
        
    Returns:
        List[DocumentResponse]: Matching documents
    """
    try:
        tenant_id = current_tenant.id
        
        # Build metadata filters
        metadata_filters = {}
        if author:
            metadata_filters["author"] = author
        if date_from:
            metadata_filters["date_from"] = date_from
        if date_to:
            metadata_filters["date_to"] = date_to
        if tags:
            metadata_filters["tags"] = [tag.strip() for tag in tags.split(",")]
        if document_type:
            metadata_filters["document_type"] = document_type
        
        # Search documents using RAG pipeline
        rag_pipeline = get_rag_pipeline()
        search_results = await rag_pipeline.search_documents(
            tenant_id=tenant_id,
            query=query,
            max_results=max_results,
            metadata_filters=metadata_filters
        )
        
        return search_results
        
    except Exception as e:
        logger.error(f"Failed to search documents: {e}", exc_info=True)
        raise internal_error(f"Failed to search documents: {str(e)}")

# =============================================================================
# QUERY HISTORY & FEEDBACK
# =============================================================================

@router.get("/history", response_model=QueryHistoryResponse)
async def get_query_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_tenant = Depends(get_current_tenant)
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
        tenant_id = current_tenant.id
        
        # Get query history from RAG pipeline
        rag_pipeline = get_rag_pipeline()
        history = await rag_pipeline.get_query_history(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size
        )
        
        return QueryHistoryResponse(
            queries=history.queries,
            total_count=history.total_count
        )
        
    except Exception as e:
        logger.error(f"Failed to get query history: {e}", exc_info=True)
        raise internal_error(f"Failed to get query history: {str(e)}")

@router.post("/feedback", response_model=QueryFeedbackResponse)
async def submit_query_feedback(
    request: QueryFeedbackRequest,
    current_tenant = Depends(get_current_tenant)
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
        tenant_id = current_tenant.id
        
        # Submit feedback to RAG pipeline
        rag_pipeline = get_rag_pipeline()
        result = await rag_pipeline.submit_query_feedback(
            tenant_id=tenant_id,
            query_id=request.query_id,
            rating=request.rating,
            feedback=request.feedback,
            helpful=request.helpful
        )
        
        return QueryFeedbackResponse(
            success=result.success,
            message=result.message
        )
        
    except Exception as e:
        logger.error(f"Failed to submit query feedback: {e}", exc_info=True)
        raise internal_error(f"Failed to submit feedback: {str(e)}")

# =============================================================================
# QUERY CONFIGURATION & STATISTICS
# =============================================================================

@router.get("/config")
async def get_query_config(
    current_tenant = Depends(get_current_tenant)
):
    """
    Get query configuration for the current tenant.
    
    Args:
        current_tenant: Current tenant (from auth)
        
    Returns:
        dict: Query configuration
    """
    try:
        tenant_id = current_tenant.id
        
        # Get query configuration from RAG pipeline
        rag_pipeline = get_rag_pipeline()
        config = await rag_pipeline.get_query_config(tenant_id=tenant_id)
        
        return config
        
    except Exception as e:
        logger.error(f"Failed to get query config: {e}", exc_info=True)
        raise internal_error(f"Failed to get query configuration: {str(e)}")

@router.put("/config")
async def update_query_config(
    config: dict,
    current_tenant = Depends(get_current_tenant)
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
        tenant_id = current_tenant.id
        
        # Update query configuration in RAG pipeline
        rag_pipeline = get_rag_pipeline()
        updated_config = await rag_pipeline.update_query_config(
            tenant_id=tenant_id,
            config=config
        )
        
        return updated_config
        
    except Exception as e:
        logger.error(f"Failed to update query config: {e}", exc_info=True)
        raise internal_error(f"Failed to update query configuration: {str(e)}")

@router.get("/stats")
async def get_query_stats(
    current_tenant = Depends(get_current_tenant)
):
    """
    Get query statistics for the current tenant.
    
    Args:
        current_tenant: Current tenant (from auth)
        
    Returns:
        dict: Query statistics
    """
    try:
        tenant_id = current_tenant.id
        
        # Get query statistics from RAG pipeline
        rag_pipeline = get_rag_pipeline()
        stats = await rag_pipeline.get_query_stats(tenant_id=tenant_id)
        
        return {
            "tenant_id": tenant_id,
            "total_queries": stats.get("total_queries", 0),
            "successful_queries": stats.get("successful_queries", 0),
            "failed_queries": stats.get("failed_queries", 0),
            "average_processing_time": stats.get("average_processing_time", 0.0),
            "average_confidence": stats.get("average_confidence", 0.0),
            "most_common_queries": stats.get("most_common_queries", []),
            "query_trends": stats.get("query_trends", {}),
            "feedback_stats": stats.get("feedback_stats", {})
        }
        
    except Exception as e:
        logger.error(f"Failed to get query stats: {e}", exc_info=True)
        raise internal_error(f"Failed to get query statistics: {str(e)}")

@router.post("/validate", response_model=dict)
async def validate_query(
    request: dict,
    current_tenant = Depends(get_current_tenant)
):
    """
    Validate a query without processing it.
    
    Args:
        request: Query validation request with 'query' field
        current_tenant: Current tenant (from auth)
        
    Returns:
        dict: Validation result
    """
    try:
        tenant_id = current_tenant.id
        query = request.get("query", "")
        
        if not query:
            raise ValidationErrorCustom("Query is required")
        
        # Validate query using RAG pipeline
        rag_pipeline = get_rag_pipeline()
        validation_result = await rag_pipeline.validate_query(
            tenant_id=tenant_id,
            query=query
        )
        
        return {
            "query": query,
            "is_valid": validation_result.is_valid,
            "suggestions": validation_result.suggestions,
            "estimated_tokens": validation_result.estimated_tokens,
            "estimated_cost": validation_result.estimated_cost
        }
        
    except Exception as e:
        logger.error(f"Failed to validate query: {e}", exc_info=True)
        raise internal_error(f"Failed to validate query: {str(e)}") 