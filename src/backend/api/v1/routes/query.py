"""
Query processing API endpoints for the Enterprise RAG Platform.

Handles natural language queries and returns responses with source citations.
"""

from fastapi import APIRouter, Depends, HTTPException
import logging

from src.backend.core.rag_pipeline import get_rag_pipeline, RAGPipeline
from src.backend.models.api_models import QueryRequest, QueryResponse, SourceCitation
from src.backend.middleware.tenant_context import get_tenant_from_header

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("", response_model=QueryResponse)
async def process_query(
    request: QueryRequest,
    tenant_id: str = Depends(get_tenant_from_header),
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline)
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
        
        # The rag_response.sources should already be in the correct format,
        # but creating new SourceCitation objects ensures type safety.
        sources = [
            SourceCitation(
                id=source.id,
                text=source.text,
                score=source.score,
                source=source.source,
                page_number=source.page_number,
                document_id=source.document_id
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