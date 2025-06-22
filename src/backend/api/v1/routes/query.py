"""
Query processing API endpoints for the Enterprise RAG Platform.

Handles natural language queries and returns responses with source citations.
"""

from fastapi import APIRouter, Depends, Security, HTTPException
from sqlalchemy.orm import Session
from typing import List
import logging
from datetime import datetime, timezone

from src.backend.db.session import get_db
from src.backend.core.rag_pipeline import get_rag_pipeline
from src.backend.models.api_models import QueryRequest, QueryResponse, QueryHistory, SourceCitation
from src.backend.middleware.auth import get_current_tenant, require_api_key

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("", response_model=QueryResponse)
# @require_api_key(scopes=["query:read"])  # Temporarily disabled for development
async def process_query(
    request: QueryRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(lambda: "default"),  # Default tenant for development
    rag_pipeline = Depends(get_rag_pipeline)
):
    """
    Processes a natural language query through the RAG pipeline.
    """
    if not request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    logger.info(f"Received query from tenant '{tenant_id}': {request.query}")
    
    try:
        rag_response = await rag_pipeline.process_query(
            query=request.query, 
            tenant_id=tenant_id
        )
        
        # Convert RAGSource to SourceCitation
        sources = [
            SourceCitation(
                id=source.id,
                text=source.text,
                score=source.score,
                filename=source.filename,
                page_number=source.page_number,
                chunk_index=source.chunk_index
            )
            for source in rag_response.sources
        ]
        
        return QueryResponse(
            query=rag_response.query,
            answer=rag_response.answer,
            sources=sources,
            confidence=rag_response.confidence,
            processing_time=rag_response.processing_time,
            llm_metadata=rag_response.llm_metadata
        )
    except Exception as e:
        logger.error(f"Error processing query for tenant '{tenant_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process query.")


@router.get("/history", response_model=QueryHistory)
# @require_api_key(scopes=["query:read"])  # Temporarily disabled for development
async def get_query_history(
    page: int = 1,
    page_size: int = 20,
    tenant_id: str = Depends(lambda: "default"),  # Default tenant for development
    db: Session = Depends(get_db),
):
    """
    Get query history for the current tenant.
    
    Returns paginated list of recent queries and their responses.
    """
    try:
        # TODO: Implement actual query history storage and retrieval
        logger.info(f"Retrieving query history for tenant {tenant_id}, page {page}")
        
        # Mock query history for now
        mock_queries = []
        
        return QueryHistory(
            queries=mock_queries,
            total_count=0,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Failed to retrieve query history for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve query history"
        )


@router.get("/{query_id}", response_model=QueryResponse)
# @require_api_key(scopes=["query:read"])  # Temporarily disabled for development
async def get_query_result(
    query_id: str,
    tenant_id: str = Depends(lambda: "default"),  # Default tenant for development
    db: Session = Depends(get_db),
):
    """
    Get a specific query result by ID.
    
    Returns the query result with all associated metadata and sources.
    """
    try:
        logger.info(f"Retrieving query result {query_id} for tenant {tenant_id}")
        
        # TODO: Implement actual query result storage and retrieval
        raise HTTPException(status_code=404, detail="Query not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve query result {query_id} for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve query result"
        )


@router.delete("/{query_id}")
# @require_api_key(scopes=["query:write"])  # Temporarily disabled for development
async def delete_query_result(
    query_id: str,
    tenant_id: str = Depends(lambda: "default"),  # Default tenant for development
    db: Session = Depends(get_db),
):
    """
    Delete a specific query result.
    
    Removes the query result from history (if implemented).
    """
    try:
        logger.info(f"Deleting query result {query_id} for tenant {tenant_id}")
        
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