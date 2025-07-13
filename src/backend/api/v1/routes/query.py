"""
RAG Query API Routes - Simplified Implementation
"""

import time
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.dependencies import get_current_tenant_dep
from src.backend.database import get_async_db
from src.backend.models.database import Tenant
from src.backend.core.database_operations import search_embeddings
from src.backend.core.embedding_engine import SingletonEmbeddingModel, EmbeddingModel

router = APIRouter()


@router.post("/")
async def process_query(
    request_data: Dict[str, Any],
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    db: AsyncSession = Depends(get_async_db)
):
    """Process a RAG query - simplified semantic search"""
    
    try:
        query = request_data.get("query", "").strip()
        if not query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query cannot be empty"
            )
        
        max_sources = request_data.get("max_sources", 5)
        
        start_time = time.time()
        
        # Get embedding model
        model = SingletonEmbeddingModel.get_model(EmbeddingModel.MINI_LM.value)
        
        # Generate query embedding
        query_embedding = model.encode([query], convert_to_tensor=False, show_progress_bar=False)[0]
        
        # Search for similar embeddings
        similar_chunks = await search_embeddings(
            db=db,
            tenant_slug=current_tenant.slug,
            query_embedding=query_embedding.tolist() if hasattr(query_embedding, 'tolist') else list(query_embedding),
            limit=max_sources
        )
        
        processing_time = time.time() - start_time
        
        # Format sources
        sources = []
        for chunk in similar_chunks:
            sources.append({
                "text": chunk.text,
                "chunk_index": chunk.chunk_index,
                "file_id": str(chunk.file_id),
                "token_count": chunk.token_count
            })
        
        # Simple answer (just concatenate top chunks for now)
        if sources:
            answer = "Based on the documents: " + " ".join([source["text"][:200] + "..." for source in sources[:3]])
        else:
            answer = "No relevant information found in the documents."
        
        return {
            "query": query,
            "answer": answer,
            "sources": sources,
            "confidence": 0.8 if sources else 0.0,
            "processing_time": processing_time,
            "method": "simplified_semantic_search",
            "tenant_id": current_tenant.slug
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process query: {str(e)}"
        )


@router.post("/search")
async def semantic_search(
    request: Dict[str, Any],
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    db: AsyncSession = Depends(get_async_db)
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
        
        # Get embedding model
        model = SingletonEmbeddingModel.get_model(EmbeddingModel.MINI_LM.value)
        
        # Generate query embedding
        query_embedding = model.encode([query], convert_to_tensor=False, show_progress_bar=False)[0]
        
        # Search for similar embeddings
        similar_chunks = await search_embeddings(
            db=db,
            tenant_slug=current_tenant.slug,
            query_embedding=query_embedding.tolist() if hasattr(query_embedding, 'tolist') else list(query_embedding),
            limit=max_results
        )
        
        # Format results
        results = []
        for chunk in similar_chunks:
            results.append({
                "text": chunk.text,
                "chunk_index": chunk.chunk_index,
                "file_id": str(chunk.file_id),
                "token_count": chunk.token_count
            })
        
        return {
            "query": query,
            "results": results,
            "total_results": len(results),
            "method": "simplified_semantic_search"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform search: {str(e)}"
        )


@router.post("/validate")
async def validate_query(
    request: Dict[str, Any],
    current_tenant: Tenant = Depends(get_current_tenant_dep)
):
    """Validate a query without processing it"""
    try:
        query = request.get("query", "")
        
        # Simple query validation
        validation = {
            "query": query,
            "is_valid": len(query.strip()) > 0,
            "length": len(query),
            "word_count": len(query.split()),
            "tenant_id": current_tenant.slug,
            "status": "simplified_validation"
        }
        
        return validation
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate query: {str(e)}"
        )