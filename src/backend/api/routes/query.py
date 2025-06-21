"""
Query processing API endpoints for the Enterprise RAG Platform.

Handles natural language queries and returns responses with source citations.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import time
import logging
from datetime import datetime

from ...core.rag_pipeline import RAGPipeline
from ...core.embeddings import EmbeddingService
from ...utils.vector_store import VectorStoreManager
from ...middleware.mock_tenant import get_current_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter()

# Local dependency functions (will be overridden by main app)
def get_embedding_service() -> EmbeddingService:
    """Get embedding service - will be overridden by main app dependency."""
    return EmbeddingService()

def get_vector_store_manager() -> VectorStoreManager:
    """Get vector store manager - will be overridden by main app dependency."""
    return VectorStoreManager()

# Request/Response Models
class QueryRequest(BaseModel):
    """Request model for query processing."""
    query: str = Field(..., min_length=1, max_length=1000, description="Natural language query")
    max_sources: Optional[int] = Field(default=5, ge=1, le=20, description="Maximum number of source citations")
    include_metadata: Optional[bool] = Field(default=True, description="Include document metadata in response")
    rerank: Optional[bool] = Field(default=True, description="Apply reranking to improve relevance")
    
    @validator('query')
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty or whitespace only')
        return v.strip()


class SourceCitation(BaseModel):
    """Source citation model."""
    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Source document filename")
    chunk_text: str = Field(..., description="Relevant text excerpt")
    page_number: Optional[int] = Field(None, description="Page number in source document")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Relevance confidence score")
    chunk_index: int = Field(..., ge=0, description="Chunk index within document")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class QueryResponse(BaseModel):
    """Response model for query processing."""
    query_id: str = Field(..., description="Unique query identifier")
    query: str = Field(..., description="Original query text")
    answer: str = Field(..., description="Generated answer")
    sources: List[SourceCitation] = Field(default_factory=list, description="Source citations")
    processing_time: float = Field(..., description="Processing time in seconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Query timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional response metadata")


class QueryHistory(BaseModel):
    """Query history model."""
    queries: List[QueryResponse] = Field(default_factory=list, description="Recent queries")
    total_count: int = Field(..., description="Total number of queries")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of queries per page")


# Dependency to get RAG pipeline
async def get_rag_pipeline(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store_manager: VectorStoreManager = Depends(get_vector_store_manager),
    tenant_id: str = Depends(get_current_tenant_id)
) -> RAGPipeline:
    """Get RAG pipeline for the current tenant."""
    try:
        return RAGPipeline(
            embedding_service=embedding_service,
            vector_store_manager=vector_store_manager,
            tenant_id=tenant_id
        )
    except Exception as e:
        logger.error(f"Failed to initialize RAG pipeline for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize query processing service"
        )


@router.post("/query", response_model=QueryResponse)
async def process_query(
    request: QueryRequest,
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Process a natural language query and return an answer with source citations.
    
    This endpoint processes natural language queries using the RAG pipeline,
    returning generated answers along with relevant source citations.
    """
    start_time = time.time()
    query_id = f"{tenant_id}-{int(time.time() * 1000)}"
    
    logger.info(f"Processing query {query_id} for tenant {tenant_id}: {request.query[:100]}...")
    
    try:
        # Process the query through RAG pipeline
        result = await rag_pipeline.process_query(
            query=request.query,
            max_sources=request.max_sources,
            include_metadata=request.include_metadata,
            rerank=request.rerank
        )
        
        processing_time = time.time() - start_time
        
        # Convert result to response format
        sources = [
            SourceCitation(
                document_id=source.get('document_id', ''),
                filename=source.get('filename', ''),
                chunk_text=source.get('chunk_text', ''),
                page_number=source.get('page_number'),
                confidence_score=source.get('confidence_score', 0.0),
                chunk_index=source.get('chunk_index', 0),
                metadata=source.get('metadata', {})
            )
            for source in result.get('sources', [])
        ]
        
        response = QueryResponse(
            query_id=query_id,
            query=request.query,
            answer=result.get('answer', ''),
            sources=sources,
            processing_time=processing_time,
            metadata={
                'tenant_id': tenant_id,
                'model_used': result.get('model_used', 'unknown'),
                'total_chunks_searched': result.get('total_chunks_searched', 0),
                'reranked': request.rerank
            }
        )
        
        logger.info(f"Query {query_id} completed in {processing_time:.3f}s with {len(sources)} sources")
        
        return response
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Query {query_id} failed after {processing_time:.3f}s: {e}")
        
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(e)}"
        )


@router.get("/query/history", response_model=QueryHistory)
async def get_query_history(
    page: int = 1,
    page_size: int = 20,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get query history for the current tenant.
    
    Returns paginated list of recent queries and their responses.
    """
    try:
        # TODO: Implement actual query history storage and retrieval
        # For now, return mock data
        
        logger.info(f"Retrieving query history for tenant {tenant_id}, page {page}")
        
        # Mock query history
        mock_queries = [
            QueryResponse(
                query_id=f"{tenant_id}-{i}",
                query=f"Sample query {i}",
                answer=f"Sample answer {i}",
                sources=[],
                processing_time=1.5,
                metadata={'tenant_id': tenant_id}
            )
            for i in range(1, 6)
        ]
        
        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_queries = mock_queries[start_idx:end_idx]
        
        return QueryHistory(
            queries=paginated_queries,
            total_count=len(mock_queries),
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Failed to retrieve query history for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve query history"
        )


@router.get("/query/{query_id}", response_model=QueryResponse)
async def get_query_result(
    query_id: str,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get a specific query result by ID.
    
    Returns the query result with all associated metadata and sources.
    """
    try:
        logger.info(f"Retrieving query result {query_id} for tenant {tenant_id}")
        
        # TODO: Implement actual query result storage and retrieval
        # For now, return mock data
        
        # Validate query ID format
        if not query_id.startswith(tenant_id):
            raise HTTPException(
                status_code=404,
                detail="Query not found"
            )
        
        # Mock query result
        mock_result = QueryResponse(
            query_id=query_id,
            query="Sample query",
            answer="Sample answer",
            sources=[],
            processing_time=1.5,
            metadata={'tenant_id': tenant_id}
        )
        
        return mock_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve query result {query_id} for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve query result"
        )


@router.delete("/query/{query_id}")
async def delete_query_result(
    query_id: str,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Delete a specific query result.
    
    Removes the query result from history (if implemented).
    """
    try:
        logger.info(f"Deleting query result {query_id} for tenant {tenant_id}")
        
        # Validate query ID format
        if not query_id.startswith(tenant_id):
            raise HTTPException(
                status_code=404,
                detail="Query not found"
            )
        
        # TODO: Implement actual query result deletion
        
        return {"message": "Query result deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete query result {query_id} for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete query result"
        ) 