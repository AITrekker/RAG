"""Vector retrieval and search for RAG system."""

import time
from typing import List, Dict, Any, Optional
from uuid import UUID
import requests
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from src.backend.models.database import EmbeddingChunk, File
from src.backend.services.embedding_service import EmbeddingService
from .base import Query, RetrievedChunk, RAGContext, RetrieverInterface

logger = logging.getLogger(__name__)

class VectorRetriever(RetrieverInterface):
    """Handles vector similarity search and context retrieval."""
    
    def __init__(self, session: AsyncSession, qdrant_url: str = "http://localhost:6333"):
        self.session = session
        self.qdrant_url = qdrant_url
        self.embedding_service = EmbeddingService(session)
        self._embedding_model = None
    
    async def search(self, query: Query) -> List[RetrievedChunk]:
        """Perform vector search with tenant isolation."""
        start_time = time.time()
        
        try:
            # Generate query embedding
            query_embedding = await self._generate_query_embedding(query.text)
            
            # Build Qdrant query with tenant filtering
            import os
            environment = os.getenv("RAG_ENVIRONMENT", "development")
            collection_name = f"documents_{environment}"
            search_payload = self._build_search_payload(query, query_embedding)
            
            # Perform vector search
            response = requests.post(
                f"{self.qdrant_url}/collections/{collection_name}/points/search",
                json=search_payload,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Qdrant search failed: {response.status_code} - {response.text}")
                return []
            
            search_results = response.json()
            
            # Convert to RetrievedChunk objects
            chunks = await self._convert_search_results(search_results, query.tenant_id)
            
            # Apply post-search filtering
            filtered_chunks = self._apply_filters(chunks, query.filters)
            
            logger.info(f"Vector search completed: {len(filtered_chunks)} chunks in {time.time() - start_time:.2f}s")
            return filtered_chunks
            
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    async def get_context(self, query: Query) -> RAGContext:
        """Get complete context for answer generation."""
        start_time = time.time()
        
        # Perform search
        chunks = await self.search(query)
        
        # Build context
        context = RAGContext(
            chunks=chunks,
            total_chunks=len(chunks),
            search_query=query.text,
            filters_applied=query.filters,
            retrieval_time=time.time() - start_time
        )
        
        return context
    
    def _build_search_payload(self, query: Query, query_embedding: List[float]) -> Dict[str, Any]:
        """Build Qdrant search payload."""
        payload = {
            "vector": query_embedding,
            "limit": query.max_results * 2,  # Get extra for filtering
            "score_threshold": query.min_score,
            "with_payload": True,
            "with_vectors": False
        }
        
        # Add tenant filtering - always include for multitenancy
        qdrant_filter = self._build_qdrant_filter(query.filters or {}, query.tenant_id)
        if qdrant_filter:
            payload["filter"] = qdrant_filter
        
        return payload
    
    def _build_qdrant_filter(self, filters: Dict[str, Any], tenant_id: UUID) -> Dict[str, Any]:
        """Build Qdrant filter from query filters."""
        must_conditions = [
            {
                "key": "tenant_id",
                "match": {"value": str(tenant_id)}
            }
        ]
        
        # File type filters
        if "file_types" in filters:
            file_type_conditions = []
            for file_type in filters["file_types"]:
                file_type_conditions.append({
                    "key": "metadata.file_type",
                    "match": {"value": file_type}
                })
            
            if file_type_conditions:
                must_conditions.append({
                    "should": file_type_conditions
                })
        
        # Filename filter
        if "filename" in filters:
            must_conditions.append({
                "key": "metadata.filename", 
                "match": {"value": filters["filename"]}
            })
        
        return {
            "must": must_conditions
        } if len(must_conditions) > 1 else {"must": must_conditions[0]}
    
    async def _convert_search_results(self, search_results: Dict[str, Any], tenant_id: UUID) -> List[RetrievedChunk]:
        """Convert Qdrant search results to RetrievedChunk objects."""
        chunks = []
        
        if "result" not in search_results:
            return chunks
        
        # Get Qdrant point IDs from search results
        qdrant_point_ids = []
        scores = {}
        
        for result in search_results["result"]:
            point_id = result["id"]  # Use the Qdrant point ID
            if point_id:
                qdrant_point_ids.append(point_id)
                scores[point_id] = result["score"]
        
        if not qdrant_point_ids:
            return chunks
        
        # Fetch chunk details from PostgreSQL using qdrant_point_id
        try:
            query_stmt = select(EmbeddingChunk, File).join(
                File, EmbeddingChunk.file_id == File.id
            ).where(
                and_(
                    EmbeddingChunk.qdrant_point_id.in_(qdrant_point_ids),
                    EmbeddingChunk.tenant_id == tenant_id,
                    File.deleted_at.is_(None)
                )
            )
            
            result = await self.session.execute(query_stmt)
            chunk_data = result.all()
            
            for chunk, file in chunk_data:
                retrieved_chunk = RetrievedChunk(
                    chunk_id=chunk.id,
                    content=chunk.chunk_content,
                    file_id=chunk.file_id,
                    filename=file.filename,
                    score=scores.get(str(chunk.qdrant_point_id), 0.0),
                    chunk_index=chunk.chunk_index,
                    file_path=file.file_path,
                    metadata={
                        "file_type": file.mime_type or "unknown",
                        "file_size": file.file_size,
                        "word_count": chunk.token_count,
                        "created_at": file.created_at.isoformat() if file.created_at else None
                    }
                )
                chunks.append(retrieved_chunk)
        
        except Exception as e:
            logger.error(f"Error fetching chunk details from PostgreSQL: {e}")
        
        # Sort by score (highest first)
        chunks.sort(key=lambda x: x.score, reverse=True)
        
        return chunks
    
    def _apply_filters(self, chunks: List[RetrievedChunk], filters: Dict[str, Any]) -> List[RetrievedChunk]:
        """Apply additional filters to search results."""
        if not filters:
            return chunks
        
        filtered_chunks = chunks
        
        # Temporal filtering (basic implementation)
        if "temporal" in filters:
            if filters["temporal"] == "recent":
                # Sort by creation date, prefer newer files
                filtered_chunks.sort(key=lambda x: x.metadata.get("created_at", ""), reverse=True)
            elif filters["temporal"] == "old":
                # Sort by creation date, prefer older files  
                filtered_chunks.sort(key=lambda x: x.metadata.get("created_at", ""))
        
        return filtered_chunks
    
    async def search_with_keywords(self, query: Query, keywords: List[str]) -> List[RetrievedChunk]:
        """Perform hybrid search combining vector and keyword matching."""
        # Get vector results
        vector_chunks = await self.search(query)
        
        # Filter by keywords in content
        keyword_filtered = []
        for chunk in vector_chunks:
            content_lower = chunk.content.lower()
            if any(keyword.lower() in content_lower for keyword in keywords):
                # Boost score for keyword matches
                chunk.score *= 1.2
                keyword_filtered.append(chunk)
        
        # Re-sort by boosted scores
        keyword_filtered.sort(key=lambda x: x.score, reverse=True)
        
        return keyword_filtered
    
    async def get_similar_chunks(self, chunk_id: UUID, tenant_id: UUID, limit: int = 5) -> List[RetrievedChunk]:
        """Find chunks similar to a given chunk."""
        try:
            # Get the source chunk
            result = await self.session.execute(
                select(EmbeddingChunk).where(
                    and_(
                        EmbeddingChunk.id == chunk_id,
                        EmbeddingChunk.tenant_id == tenant_id
                    )
                )
            )
            source_chunk = result.scalar_one_or_none()
            
            if not source_chunk:
                return []
            
            # Use chunk content as query  
            fake_query = Query(
                text=source_chunk.chunk_content,
                tenant_id=tenant_id,
                max_results=limit + 1  # +1 to exclude self
            )
            
            similar_chunks = await self.search(fake_query)
            
            # Remove the source chunk from results
            return [chunk for chunk in similar_chunks if chunk.chunk_id != chunk_id][:limit]
            
        except Exception as e:
            logger.error(f"Error finding similar chunks: {e}")
            return []
    
    async def _generate_query_embedding(self, text: str) -> List[float]:
        """Generate embedding for query text."""
        try:
            # Initialize model if needed
            if self._embedding_model is None:
                from sentence_transformers import SentenceTransformer
                import torch
                
                # Use GPU if available and compatible for maximum performance
                device = 'cpu'  # Default to CPU for compatibility
                
                # For now, always use CPU due to RTX 5070 compatibility issues
                # TODO: Enable GPU when PyTorch CUDA 12.8 is installed
                if torch.cuda.is_available():
                    logger.warning("CUDA available but using CPU due to RTX 5070 compatibility (sm_120 vs sm_50-90)")
                
                self._embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device=device)
                logger.info(f"Initialized embedding model on device: {device}")
            
            # Generate embedding
            embedding = self._embedding_model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            # Return zero vector as fallback
            return [0.0] * 384