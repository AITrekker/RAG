"""Complete RAG pipeline orchestration."""

import time
import logging
from typing import Optional, AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .base import RAGResponse, RAGPipelineInterface
from .query_processor import QueryProcessor
from .retriever import VectorRetriever
from .context_ranker import ContextRanker

logger = logging.getLogger(__name__)

class RAGPipeline(RAGPipelineInterface):
    """Orchestrates the complete RAG workflow."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.query_processor = QueryProcessor()
        self.retriever = VectorRetriever(session)
        self.ranker = ContextRanker()
    
    async def process_query(self, raw_query: str, tenant_id: UUID, user_id: Optional[UUID] = None) -> RAGResponse:
        """Process complete RAG query."""
        start_time = time.time()
        
        try:
            # Step 1: Process query
            logger.info(f"Processing query for tenant {tenant_id}: {raw_query[:100]}")
            query = self.query_processor.process_query(raw_query, tenant_id, user_id)
            
            # Step 2: Retrieve context
            context = await self.retriever.get_context(query)
            
            # Step 3: Rank and filter context
            ranked_chunks = self.ranker.rank_chunks(context.chunks, query.text)
            filtered_chunks = self.ranker.filter_duplicates(ranked_chunks)
            diverse_chunks = self.ranker.apply_diversity(filtered_chunks)
            
            # Update context with processed chunks
            context.chunks = diverse_chunks
            
            # Step 4: Generate response (simplified for now)
            answer, sources = await self._generate_simple_response(context, query.text)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Build response
            response = RAGResponse(
                answer=answer,
                sources=sources,
                confidence=self._calculate_confidence(context),
                context_used=[chunk.content[:200] + "..." for chunk in context.chunks],
                processing_time=processing_time,
                query=raw_query,
                tenant_id=tenant_id,
                metadata={
                    "chunks_found": len(context.chunks),
                    "unique_sources": len(context.unique_sources),
                    "filters_applied": query.filters,
                    "retrieval_time": context.retrieval_time
                }
            )
            
            logger.info(f"RAG query completed in {processing_time:.2f}s with {len(context.chunks)} chunks")
            return response
            
        except Exception as e:
            logger.error(f"Error in RAG pipeline: {e}")
            # Return error response
            return RAGResponse(
                answer=f"Sorry, I encountered an error processing your query: {str(e)}",
                sources=[],
                confidence=0.0,
                context_used=[],
                processing_time=time.time() - start_time,
                query=raw_query,
                tenant_id=tenant_id,
                metadata={"error": str(e)}
            )
    
    async def stream_response(self, raw_query: str, tenant_id: UUID, user_id: Optional[UUID] = None) -> AsyncIterator[str]:
        """Stream RAG response (basic implementation)."""
        # For now, just yield the complete response
        # In future, this would stream from LLM
        response = await self.process_query(raw_query, tenant_id, user_id)
        
        # Simulate streaming by yielding words
        words = response.answer.split()
        for word in words:
            yield word + " "
            # Small delay to simulate streaming
            import asyncio
            await asyncio.sleep(0.1)
    
    async def _generate_simple_response(self, context, query: str) -> tuple[str, list]:
        """Generate simple response without LLM (for testing)."""
        if not context.chunks:
            return "I couldn't find any relevant information to answer your question.", []
        
        # Simple template-based response
        sources_info = []
        for i, chunk in enumerate(context.chunks[:3], 1):
            sources_info.append({
                "filename": chunk.filename,
                "chunk_index": chunk.chunk_index,
                "relevance_score": round(chunk.score, 2),
                "excerpt": chunk.content[:150] + "..." if len(chunk.content) > 150 else chunk.content
            })
        
        # Build simple answer
        if len(context.chunks) == 1:
            answer = f"Based on the information in {context.chunks[0].filename}, here's what I found:\\n\\n"
            answer += context.chunks[0].content[:500]
            if len(context.chunks[0].content) > 500:
                answer += "..."
        else:
            answer = f"I found relevant information in {len(context.chunks)} sources:\\n\\n"
            for chunk in context.chunks[:2]:
                answer += f"From {chunk.filename}:\\n{chunk.content[:300]}"
                if len(chunk.content) > 300:
                    answer += "..."
                answer += "\\n\\n"
        
        return answer, sources_info
    
    def _calculate_confidence(self, context) -> float:
        """Calculate confidence score for the response."""
        if not context.chunks:
            return 0.0
        
        # Base confidence on:
        # 1. Number of relevant chunks found
        # 2. Average relevance score
        # 3. Source diversity
        
        chunk_count_factor = min(1.0, len(context.chunks) / 3.0)  # Normalize to max 3 chunks
        avg_score = sum(chunk.score for chunk in context.chunks) / len(context.chunks)
        diversity_factor = min(1.0, len(context.unique_sources) / 2.0)  # Normalize to max 2 sources
        
        confidence = (chunk_count_factor * 0.4 + avg_score * 0.4 + diversity_factor * 0.2)
        return round(confidence, 2)
    
    async def get_query_suggestions(self, partial_query: str, tenant_id: UUID, limit: int = 5) -> list[str]:
        """Get query suggestions based on partial input."""
        # Simple implementation - could be enhanced with ML
        common_queries = [
            "What is our work from home policy?",
            "What are the company benefits?",
            "How do I request vacation time?",
            "What is the dress code policy?",
            "How do I contact HR?",
            "What are the office hours?",
            "What is the remote work policy?",
            "How do I submit expenses?",
            "What are the holiday dates?",
            "How do I schedule a meeting?"
        ]
        
        if not partial_query:
            return common_queries[:limit]
        
        # Filter suggestions based on partial query
        partial_lower = partial_query.lower()
        suggestions = [q for q in common_queries if partial_lower in q.lower()]
        
        return suggestions[:limit]
    
    async def get_related_questions(self, query: str, tenant_id: UUID, limit: int = 3) -> list[str]:
        """Get related questions based on current query."""
        # Simple rule-based related questions
        query_lower = query.lower()
        
        related_map = {
            "work from home": [
                "What equipment is provided for remote work?",
                "How often can I work from home?",
                "What are the remote work requirements?"
            ],
            "benefits": [
                "How do I enroll in health insurance?",
                "What is the retirement plan?",
                "Do we have dental coverage?"
            ],
            "vacation": [
                "How much vacation time do I get?",
                "How far in advance should I request time off?",
                "What is the vacation approval process?"
            ],
            "policy": [
                "Where can I find all company policies?",
                "How often are policies updated?",
                "Who do I contact about policy questions?"
            ]
        }
        
        for key, questions in related_map.items():
            if key in query_lower:
                return questions[:limit]
        
        return []