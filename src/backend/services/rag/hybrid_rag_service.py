"""
Hybrid RAG Service that uses LlamaIndex selectively while maintaining our architecture
"""

from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
import asyncio
import time

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from src.backend.models.database import File, EmbeddingChunk, Tenant
from src.backend.config.settings import get_settings

settings = get_settings()


class HybridRAGService:
    """
    RAG service that intelligently uses LlamaIndex components without their index abstractions
    
    Strategy:
    1. Use our pgvector for all vector storage/retrieval
    2. Use LlamaIndex only for response synthesis when beneficial
    3. Keep our simplified query processing
    4. Optionally enhance with LlamaIndex's response generation
    """
    
    def __init__(self, db_session: AsyncSession, embedding_service):
        self.db = db_session
        self.embedding_service = embedding_service
        self._response_synthesizer = None
        self._llm_model = None
        self._llamaindex_available = False
    
    async def initialize(self):
        """Initialize LlamaIndex components we actually want to use"""
        try:
            # Import only response synthesis components
            from llama_index.core.response_synthesizers import ResponseMode, get_response_synthesizer
            from llama_index.core.llms import ChatMessage, MessageRole
            
            # Try to set up HuggingFace LLM for LlamaIndex
            try:
                from llama_index.llms.huggingface import HuggingFaceLLM
                
                # Create HuggingFace LLM for LlamaIndex
                llm = HuggingFaceLLM(
                    model_name=settings.rag_llm_model,
                    tokenizer_name=settings.rag_llm_model,
                    device_map="auto",
                    max_new_tokens=settings.rag_max_new_tokens,  # Set directly, not in generate_kwargs
                    model_kwargs={"torch_dtype": "auto"},
                    generate_kwargs={
                        "temperature": settings.rag_temperature,
                        "do_sample": settings.rag_do_sample,
                        "top_p": settings.rag_top_p,
                        "top_k": settings.rag_top_k,
                        # Removed max_new_tokens from here to avoid conflict
                    }
                )
                
                # Create response synthesizer with our HuggingFace LLM
                self._response_synthesizer = get_response_synthesizer(
                    response_mode=ResponseMode.COMPACT,
                    llm=llm,
                    use_async=True,
                    streaming=False
                )
                print("✓ LlamaIndex response synthesizer initialized with HuggingFace LLM")
                
            except Exception as llm_error:
                print(f"⚠️ Could not initialize HuggingFace LLM for LlamaIndex: {llm_error}")
                print("⚠️ Falling back to simple response synthesis without LlamaIndex")
                self._response_synthesizer = None
            
            self._llamaindex_available = True
            print("✓ Hybrid RAG service initialized with LlamaIndex response synthesis")
            
        except ImportError as e:
            print(f"⚠️ LlamaIndex not available for response synthesis: {e}")
            self._llamaindex_available = False
        except Exception as e:
            print(f"⚠️ Error initializing LlamaIndex components: {e}")
            self._llamaindex_available = False
    
    async def query(
        self,
        query: str,
        tenant_id: UUID,
        max_results: int = 5,
        min_score: float = 0.7,
        use_llamaindex_synthesis: bool = True
    ) -> Dict[str, Any]:
        """
        Process RAG query using our pgvector retrieval + optional LlamaIndex synthesis
        
        This combines the best of both worlds:
        - Our fast, simple pgvector retrieval
        - LlamaIndex's advanced response synthesis (when available)
        """
        start_time = time.time()
        
        try:
            # Step 1: Use our pgvector retrieval (fast, reliable, tenant-isolated)
            similar_chunks = await self._retrieve_similar_chunks(
                query, tenant_id, max_results, min_score
            )
            
            if not similar_chunks:
                return {
                    'query': query,
                    'answer': 'No relevant information found in your documents.',
                    'sources': [],
                    'confidence': 0.0,
                    'processing_time': time.time() - start_time,
                    'method': 'no_results'
                }
            
            # Step 2: Choose response generation method
            if (use_llamaindex_synthesis and 
                self._llamaindex_available and 
                len(similar_chunks) > 2):  # Use LlamaIndex for complex multi-source responses
                
                answer = await self._llamaindex_response_synthesis(query, similar_chunks)
                method = "pgvector_retrieval + llamaindex_synthesis"
                
            else:
                # Use our simple response generation
                answer = await self._simple_response_generation(query, similar_chunks)
                method = "pgvector_retrieval + simple_synthesis"
            
            # Step 3: Build response with source attribution
            try:
                sources = await self._build_source_attribution(similar_chunks)
            except Exception as attr_error:
                print(f"⚠️ Hybrid RAG service failed: {attr_error}, falling back to traditional RAG")
                # Fallback to simple source format
                sources = [
                    {
                        'chunk_content': chunk.chunk_content,
                        'score': score,
                        'filename': f'chunk_{chunk.chunk_index}',
                        'file_id': str(chunk.file_id),
                        'chunk_index': chunk.chunk_index
                    }
                    for chunk, score in similar_chunks[:5]
                ]
            
            return {
                'query': query,
                'answer': answer,
                'sources': sources,
                'confidence': self._calculate_confidence(similar_chunks),
                'processing_time': time.time() - start_time,
                'method': method,
                'chunks_found': len(similar_chunks)
            }
            
        except Exception as e:
            print(f"❌ Error in hybrid RAG query: {e}")
            return {
                'query': query,
                'answer': f'Sorry, I encountered an error processing your query: {str(e)}',
                'sources': [],
                'confidence': 0.0,
                'processing_time': time.time() - start_time,
                'method': 'error',
                'error': str(e)
            }
    
    async def _retrieve_similar_chunks(
        self,
        query: str,
        tenant_id: UUID,
        max_results: int,
        min_score: float
    ) -> List[Tuple[EmbeddingChunk, float]]:
        """
        Use our pgvector retrieval - this stays exactly the same
        
        Key insight: We don't need LlamaIndex's vector store abstractions
        Our pgvector implementation is simpler and faster
        """
        try:
            # Generate query embedding using our embedding service
            query_embedding = await self._generate_query_embedding(query)
            if not query_embedding:
                return []
            
            # Use our pgvector similarity search
            similar_chunks = await self.embedding_service.search_similar_chunks(
                query_embedding, tenant_id, max_results
            )
            
            # Filter by minimum score
            filtered_chunks = [
                (chunk, score) for chunk, score in similar_chunks 
                if score >= min_score
            ]
            
            return filtered_chunks
            
        except Exception as e:
            print(f"❌ Error in vector retrieval: {e}")
            return []
    
    async def _generate_query_embedding(self, query: str) -> Optional[List[float]]:
        """Generate embedding for query using our embedding service"""
        try:
            # Use our existing embedding generation
            if hasattr(self.embedding_service, 'embedding_model') and self.embedding_service.model_loaded:
                embedding = self.embedding_service.embedding_model.encode([query], convert_to_tensor=False)
                return embedding[0].tolist()
            else:
                # Fallback for when embedding model not available
                return None
        except Exception as e:
            print(f"❌ Error generating query embedding: {e}")
            return None
    
    async def _llamaindex_response_synthesis(
        self,
        query: str,
        similar_chunks: List[Tuple[EmbeddingChunk, float]]
    ) -> str:
        """
        Use LlamaIndex for advanced response synthesis
        
        This is where LlamaIndex adds real value - better response generation
        """
        try:
            from llama_index.core.schema import NodeWithScore, TextNode
            from llama_index.core.query_engine import BaseQueryEngine
            
            # Convert our chunks to LlamaIndex nodes
            nodes_with_scores = []
            for chunk, score in similar_chunks:
                # Create LlamaIndex TextNode from our chunk
                node = TextNode(
                    text=chunk.chunk_content,
                    id_=str(chunk.id),
                    metadata={
                        'file_id': str(chunk.file_id),
                        'chunk_index': chunk.chunk_index,
                        'source': await self._get_chunk_source_info(chunk)
                    }
                )
                
                # Convert score to LlamaIndex format (higher is better)
                llamaindex_score = 1.0 - score  # pgvector uses distance, LlamaIndex uses similarity
                node_with_score = NodeWithScore(node=node, score=llamaindex_score)
                nodes_with_scores.append(node_with_score)
            
            # Use LlamaIndex response synthesizer
            response = await self._response_synthesizer.asynthesize(
                query=query,
                nodes=nodes_with_scores
            )
            
            return str(response)
            
        except Exception as e:
            print(f"⚠️ LlamaIndex synthesis failed, falling back to simple: {e}")
            # Fallback to simple response generation
            return await self._simple_response_generation(query, similar_chunks)
    
    async def _simple_response_generation(
        self,
        query: str,
        similar_chunks: List[Tuple[EmbeddingChunk, float]]
    ) -> str:
        """
        Our simple response generation (fallback)
        """
        # Get the most relevant chunks
        top_chunks = similar_chunks[:3]  # Use top 3 chunks
        
        # Simple context building
        context_parts = []
        for chunk, score in top_chunks:
            source_info = await self._get_chunk_source_info(chunk)
            context_parts.append(f"From {source_info}: {chunk.chunk_content}")
        
        context = "\n\n".join(context_parts)
        
        # Simple template-based response
        if context:
            return f"Based on your documents:\n\n{context[:1000]}..."  # Truncate if too long
        else:
            return "I couldn't find relevant information to answer your question."
    
    async def _get_chunk_source_info(self, chunk: EmbeddingChunk) -> str:
        """Get human-readable source information for a chunk"""
        try:
            # Get file information
            result = await self.db.execute(
                select(File).where(File.id == chunk.file_id)
            )
            file_record = result.scalar_one_or_none()
            
            if file_record:
                return f"{file_record.filename} (chunk {chunk.chunk_index + 1})"
            else:
                return f"Unknown source (chunk {chunk.chunk_index + 1})"
                
        except Exception as e:
            return f"Source info unavailable (chunk {chunk.chunk_index + 1})"
    
    async def _build_source_attribution(
        self,
        similar_chunks: List[Tuple[EmbeddingChunk, float]]
    ) -> List[Dict[str, Any]]:
        """Build source attribution for response"""
        sources = []
        
        # Get unique files and their details
        file_ids = list(set(chunk.file_id for chunk, _ in similar_chunks))
        
        for file_id in file_ids:
            try:
                result = await self.db.execute(
                    select(File).where(File.id == file_id)
                )
                file_record = result.scalar_one_or_none()
                
                if file_record:
                    # Get chunks from this file
                    file_chunks = [
                        (chunk, score) for chunk, score in similar_chunks 
                        if chunk.file_id == file_id
                    ]
                    
                    sources.append({
                        'filename': file_record.filename,
                        'file_id': str(file_record.id),
                        'chunks_used': len(file_chunks),
                        'avg_relevance': sum(score for _, score in file_chunks) / len(file_chunks),
                        'file_size': file_record.file_size,
                        'modified_time': file_record.updated_at.isoformat() if file_record.updated_at else None
                    })
                    
            except Exception as e:
                print(f"⚠️ Error getting source info for file {file_id}: {e}")
                continue
        
        return sources
    
    def _calculate_confidence(self, similar_chunks: List[Tuple[EmbeddingChunk, float]]) -> float:
        """Calculate confidence score based on retrieval results"""
        if not similar_chunks:
            return 0.0
        
        # Simple confidence calculation
        avg_score = sum(score for _, score in similar_chunks) / len(similar_chunks)
        
        # Convert distance to confidence (lower distance = higher confidence)
        confidence = max(0.0, min(1.0, 1.0 - avg_score))
        
        # Boost confidence if we have multiple good matches
        if len(similar_chunks) >= 3 and confidence > 0.6:
            confidence = min(1.0, confidence * 1.1)
        
        return round(confidence, 3)


# Factory function for dependency injection
async def create_hybrid_rag_service(
    db_session: AsyncSession, 
    embedding_service
) -> HybridRAGService:
    """Factory function to create and initialize hybrid RAG service"""
    service = HybridRAGService(db_session, embedding_service)
    await service.initialize()
    return service