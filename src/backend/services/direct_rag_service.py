"""
Direct RAG Service - Minimal, Bloat-Free Embedding Experimentation
No LlamaIndex dependencies - direct control over chunking, embeddings, and retrieval
"""

import time
import asyncio
from typing import List, Dict, Any, Optional
# UUID no longer needed - using string slugs
from dataclasses import dataclass

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from src.backend.models.database import File, EmbeddingChunk
from src.backend.services.file_service import FileService
from src.backend.config.settings import get_settings

settings = get_settings()


@dataclass
class RAGResult:
    """Simple RAG result structure"""
    query: str
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float
    processing_time: float
    method: str
    tenant_slug: str


class DirectRAGService:
    """
    Minimal RAG service for embedding experimentation
    
    Features:
    - Direct pgvector queries (no abstractions)
    - Multiple chunking strategies
    - Easy embedding model swapping
    - Clear performance measurement
    - Reranking experimentation ready
    """
    
    def __init__(self, db: AsyncSession, file_service: FileService, embedding_model):
        self.db = db
        self.file_service = file_service
        self.embedding_model = embedding_model
        
    async def query(
        self, 
        question: str, 
        tenant_slug: str,
        max_sources: int = 5,
        similarity_threshold: float = 0.1
    ) -> RAGResult:
        """Process RAG query with direct vector search"""
        start_time = time.time()
        
        try:
            # Generate query embedding (async to prevent blocking)
            query_embedding = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.embedding_model.encode([question])[0]
            )
            
            # Direct pgvector similarity search
            sources = await self._vector_search(
                tenant_slug=tenant_slug,
                query_embedding=query_embedding,
                max_results=max_sources,
                threshold=similarity_threshold
            )
            
            # Simple answer generation (replace with reranking experiments later)
            answer = self._generate_simple_answer(question, sources)
            
            processing_time = time.time() - start_time
            
            return RAGResult(
                query=question,
                answer=answer,
                sources=sources,
                confidence=self._calculate_confidence(sources),
                processing_time=processing_time,
                method="direct_vector_search",
                tenant_slug=tenant_slug
            )
            
        except Exception as e:
            return RAGResult(
                query=question,
                answer=f"Error processing query: {str(e)}",
                sources=[],
                confidence=0.0,
                processing_time=time.time() - start_time,
                method="error",
                tenant_slug=tenant_slug
            )
    
    async def _vector_search(
        self,
        tenant_slug: str,
        query_embedding: np.ndarray,
        max_results: int,
        threshold: float
    ) -> List[Dict[str, Any]]:
        """Direct pgvector similarity search"""
        
        # Convert numpy array to pgvector format
        embedding_list = str(list(query_embedding))
        
        # Use explicit transaction management to prevent rollbacks
        async with self.db.begin():
            # Direct pgvector query with cosine similarity - TEMPORARILY REMOVE THRESHOLD FOR DEBUGGING
            query = text("""
                SELECT 
                    ec.id,
                    ec.chunk_content,
                    ec.chunk_index,
                    ec.embedding <=> :query_embedding AS similarity_score,
                    f.filename,
                    f.id as file_id,
                    f.file_size
                FROM embedding_chunks ec
                JOIN files f ON ec.file_id = f.id
                WHERE ec.tenant_slug = :tenant_slug 
                AND f.sync_status = 'synced'
                AND f.deleted_at IS NULL
                ORDER BY ec.embedding <=> :query_embedding
                LIMIT :max_results
            """)
            
            result = await self.db.execute(
                query,
                {
                    "tenant_slug": tenant_slug,
                    "query_embedding": embedding_list,
                    "max_results": max_results
                }
            )
            
            sources = []
            for row in result.fetchall():
                sources.append({
                    "chunk_id": str(row.id),
                    "content": row.chunk_content[:500] + "..." if len(row.chunk_content) > 500 else row.chunk_content,
                    "chunk_index": row.chunk_index,
                    "similarity_score": float(row.similarity_score),
                    "filename": row.filename,
                    "file_id": str(row.file_id),
                    "file_size": row.file_size,
                    "rank": len(sources) + 1
                })
            
            return sources
    
    def _generate_simple_answer(self, question: str, sources: List[Dict[str, Any]]) -> str:
        """Simple answer generation - replace with LLM/reranking later"""
        if not sources:
            return "I couldn't find relevant information to answer your question."
        
        # Simple template-based response
        filenames = list(set(source["filename"] for source in sources))
        
        if len(sources) == 1:
            return f"Based on information from {filenames[0]}, here's what I found: {sources[0]['content'][:200]}..."
        else:
            return f"Based on {len(sources)} relevant sections from {len(filenames)} documents ({', '.join(filenames[:3])}), I found relevant information. The most relevant section: {sources[0]['content'][:200]}..."
    
    def _calculate_confidence(self, sources: List[Dict[str, Any]]) -> float:
        """Simple confidence calculation based on similarity scores"""
        if not sources:
            return 0.0
        
        # Average similarity score (lower is better for cosine distance)
        avg_distance = np.mean([source["similarity_score"] for source in sources])
        
        # Convert distance to confidence (0-1 scale)
        confidence = max(0.0, 1.0 - avg_distance)
        return round(confidence, 3)
    
    async def add_document(
        self, 
        file_content: str, 
        tenant_slug: str, 
        file_record: File
    ) -> bool:
        """Add document with direct chunking and embedding"""
        try:
            # Simple fixed-size chunking (replace with chunking experiments)
            chunks = self._chunk_text(file_content, chunk_size=512, overlap=50)
            
            # Generate embeddings for all chunks (async to prevent blocking)
            embeddings = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.embedding_model.encode([chunk["text"] for chunk in chunks])
            )
            
            # Store chunks and embeddings directly in pgvector
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_record = EmbeddingChunk(
                    file_id=file_record.id,
                    tenant_slug=tenant_slug,
                    chunk_index=i,
                    chunk_content=chunk["text"],
                    token_count=len(chunk["text"].split()),
                    embedding=list(embedding)  # Store as array for pgvector
                )
                self.db.add(chunk_record)
            
            await self.db.commit()
            return True
            
        except Exception as e:
            print(f"Error adding document: {e}")
            await self.db.rollback()
            return False
    
    def _chunk_text(
        self, 
        text: str, 
        chunk_size: int = 512, 
        overlap: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Simple fixed-size chunking - perfect starting point for chunking experiments
        
        TODO: Add chunking strategy experiments:
        - Sliding window chunking
        - Semantic chunking (sentence boundaries)
        - Document-aware chunking (paragraphs)
        - Recursive chunking
        """
        words = text.split()
        chunks = []
        
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text = " ".join(words[start:end])
            
            chunks.append({
                "text": chunk_text,
                "start_word": start,
                "end_word": end,
                "word_count": end - start
            })
            
            start = end - overlap  # Overlap for context preservation
            if start >= len(words):
                break
        
        return chunks
    
    async def get_tenant_stats(self, tenant_slug: str) -> Dict[str, Any]:
        """Get basic tenant statistics"""
        # Use explicit transaction management to prevent rollbacks
        async with self.db.begin():
            # Count files
            file_count_query = select(File).where(
                File.tenant_slug == tenant_slug,
                File.deleted_at.is_(None)
            )
            file_result = await self.db.execute(file_count_query)
            file_count = len(file_result.fetchall())
            
            # Count chunks
            chunk_count_query = select(EmbeddingChunk).where(
                EmbeddingChunk.tenant_slug == tenant_slug
            )
            chunk_result = await self.db.execute(chunk_count_query)
            chunk_count = len(chunk_result.fetchall())
            
            return {
                "tenant_id": tenant_slug,
                "file_count": file_count,
                "chunk_count": chunk_count,
                "embedding_model": getattr(self.embedding_model, 'name', 'sentence-transformers'),
                "status": "direct_rag_ready"
            }