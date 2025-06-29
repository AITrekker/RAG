"""
RAG Service - Handles query processing, retrieval, and generation
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.backend.models.database import File, EmbeddingChunk, Tenant
from src.backend.services.file_service import FileService
from src.backend.config.settings import get_settings

settings = get_settings()


@dataclass
class SearchResult:
    """Result from vector search"""
    chunk_id: UUID
    file_id: UUID
    content: str
    score: float
    metadata: Dict[str, Any]
    chunk_index: int
    filename: str


@dataclass
class RAGResponse:
    """Response from RAG query processing"""
    query: str
    answer: str
    sources: List[SearchResult]
    confidence: float
    processing_time: float
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None


class RAGService:
    """Service for RAG query processing and retrieval"""
    
    def __init__(self, db_session: AsyncSession, file_service: FileService):
        self.db = db_session
        self.file_service = file_service
        
        # TODO: Initialize LLM and embedding models
        self._llm_model = None
        self._embedding_model = None
        self._qdrant_client = None
    
    async def initialize(self):
        """Initialize RAG components"""
        try:
            # Initialize Qdrant client
            from qdrant_client import QdrantClient
            from src.backend.config.settings import get_settings
            
            settings = get_settings()
            self._qdrant_client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port
            )
            
            print(f"✓ Qdrant client initialized: {settings.qdrant_host}:{settings.qdrant_port}")
            
            # Initialize embedding model for query processing
            try:
                from sentence_transformers import SentenceTransformer
                embedding_model = getattr(settings, 'embedding_model', 'all-MiniLM-L6-v2')
                self._embedding_model = SentenceTransformer(embedding_model)
                print(f"✓ Query embedding model initialized: {embedding_model}")
            except ImportError:
                print("⚠️ sentence-transformers not available for query embeddings")
                self._embedding_model = None
            
            # TODO: Initialize LLM for answer generation
            # For now, we'll use a mock LLM
            self._llm_model = None
            print("⚠️ LLM model not initialized - using mock responses")
            
        except ImportError:
            print("⚠️ qdrant-client not available, using mock vector operations")
            self._qdrant_client = None
            self._embedding_model = None
            self._llm_model = None
        except Exception as e:
            print(f"⚠️ Failed to initialize RAG components: {e}")
            self._qdrant_client = None
            self._embedding_model = None
            self._llm_model = None
    
    async def process_query(
        self, 
        query: str, 
        tenant_id: UUID,
        max_sources: int = 5,
        confidence_threshold: float = 0.7,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> RAGResponse:
        """
        Process a RAG query with retrieval and generation
        
        Args:
            query: User query
            tenant_id: Tenant ID for isolation
            max_sources: Maximum number of sources to retrieve
            confidence_threshold: Minimum confidence score for sources
            metadata_filters: Optional metadata filters
            
        Returns:
            RAGResponse: Generated response with sources
        """
        start_time = datetime.utcnow()
        
        # Step 1: Generate query embedding
        query_embedding = await self._generate_query_embedding(query)
        
        # Step 2: Retrieve relevant chunks
        search_results = await self._search_relevant_chunks(
            query_embedding=query_embedding,
            tenant_id=tenant_id,
            max_results=max_sources * 2,  # Get extra for filtering
            metadata_filters=metadata_filters
        )
        
        # Step 3: Filter by confidence threshold
        filtered_results = [
            result for result in search_results 
            if result.score >= confidence_threshold
        ][:max_sources]
        
        # Step 4: Generate answer using LLM
        answer = await self._generate_answer(query, filtered_results)
        
        # Step 5: Calculate processing time
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        return RAGResponse(
            query=query,
            answer=answer,
            sources=filtered_results,
            confidence=sum(r.score for r in filtered_results) / len(filtered_results) if filtered_results else 0.0,
            processing_time=processing_time,
            model_used="placeholder-model",  # TODO: Use actual model name
            tokens_used=None  # TODO: Count actual tokens
        )
    
    async def _generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for the query"""
        if self._embedding_model is not None:
            try:
                # Generate real embedding
                embedding = self._embedding_model.encode([query])[0]
                return embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
            except Exception as e:
                print(f"⚠️ Error generating query embedding: {e}")
        
        # Fallback to mock embedding
        import random
        random.seed(hash(query) % 2147483647)  # Deterministic based on query
        return [random.uniform(-1, 1) for _ in range(384)]
    
    async def _search_relevant_chunks(
        self,
        query_embedding: List[float],
        tenant_id: UUID,
        max_results: int = 10,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Search for relevant chunks using vector similarity"""
        collection_name = f"tenant_{tenant_id}_documents"
        
        if self._qdrant_client is not None:
            try:
                # Build Qdrant filter
                must_conditions = [
                    {"key": "tenant_id", "match": {"value": str(tenant_id)}}
                ]
                
                # Add metadata filters if provided
                if metadata_filters:
                    for key, value in metadata_filters.items():
                        if value is not None:
                            must_conditions.append({
                                "key": f"metadata.{key}",
                                "match": {"value": value}
                            })
                
                qdrant_filter = {"must": must_conditions} if must_conditions else None
                
                # Search in Qdrant
                search_results = self._qdrant_client.search(
                    collection_name=collection_name,
                    query_vector=query_embedding,
                    limit=max_results,
                    query_filter=qdrant_filter
                )
                
                # Convert Qdrant results to SearchResult objects
                results = []
                for result in search_results:
                    payload = result.payload
                    
                    # Get chunk details from database
                    chunk_id = payload.get("chunk_id")
                    if chunk_id:
                        db_result = await self.db.execute(
                            select(EmbeddingChunk, File)
                            .join(File)
                            .where(EmbeddingChunk.id == chunk_id)
                        )
                        chunk_and_file = db_result.first()
                        
                        if chunk_and_file:
                            chunk, file = chunk_and_file
                            
                            search_result = SearchResult(
                                chunk_id=chunk.id,
                                file_id=chunk.file_id,
                                content=chunk.chunk_content,
                                score=result.score,
                                metadata={
                                    "filename": file.filename,
                                    "chunk_index": chunk.chunk_index,
                                    "file_path": file.file_path
                                },
                                chunk_index=chunk.chunk_index,
                                filename=file.filename
                            )
                            results.append(search_result)
                
                print(f"✓ Found {len(results)} relevant chunks via Qdrant")
                return results
                
            except Exception as e:
                print(f"⚠️ Qdrant search failed: {e}, falling back to database search")
        
        # Fallback: Search using database only (no vector similarity)
        return await self._fallback_database_search(tenant_id, max_results, metadata_filters)
    
    async def _fallback_database_search(
        self,
        tenant_id: UUID,
        max_results: int,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Fallback search using database when Qdrant is not available"""
        result = await self.db.execute(
            select(EmbeddingChunk, File)
            .join(File)
            .where(
                EmbeddingChunk.tenant_id == tenant_id,
                File.deleted_at.is_(None)
            )
            .limit(max_results)
        )
        
        chunks_and_files = result.all()
        search_results = []
        
        for chunk, file in chunks_and_files:
            # Mock similarity score
            import random
            random.seed(hash(chunk.chunk_content) % 2147483647)
            mock_score = random.uniform(0.6, 0.9)
            
            search_result = SearchResult(
                chunk_id=chunk.id,
                file_id=chunk.file_id,
                content=chunk.chunk_content,
                score=mock_score,
                metadata={
                    'filename': file.filename,
                    'file_path': file.file_path,
                    'chunk_index': chunk.chunk_index,
                    'token_count': chunk.token_count
                },
                chunk_index=chunk.chunk_index,
                filename=file.filename
            )
            search_results.append(search_result)
        
        # Sort by score (descending)
        search_results.sort(key=lambda x: x.score, reverse=True)
        return search_results
    
    async def _generate_answer(
        self, 
        query: str, 
        search_results: List[SearchResult]
    ) -> str:
        """Generate answer using LLM based on retrieved context"""
        if not search_results:
            return "I couldn't find relevant information to answer your question."
        
        # Build context from search results
        context_parts = []
        for i, result in enumerate(search_results):
            context_parts.append(f"[Source {i+1} - {result.filename}]: {result.content}")
        
        context = "\n\n".join(context_parts)
        
        if self._llm_model is not None:
            # Use actual LLM if available
            try:
                prompt = self._build_rag_prompt(query, context)
                answer = await self._generate_llm_response(prompt)
                return answer
            except Exception as e:
                print(f"⚠️ LLM generation failed: {e}, using fallback")
        
        # Fallback: Create a structured response based on context
        return self._generate_fallback_answer(query, search_results)
    
    def _build_rag_prompt(self, query: str, context: str) -> str:
        """Build a structured prompt for RAG"""
        return f"""You are a helpful AI assistant. Based on the provided context, answer the user's question accurately and concisely.

Context:
{context}

Question: {query}

Instructions:
- Answer based ONLY on the provided context
- If the context doesn't contain enough information, say so
- Be specific and cite which sources support your answer
- Keep your response focused and relevant

Answer:"""
    
    async def _generate_llm_response(self, prompt: str) -> str:
        """Generate response using LLM model"""
        # TODO: Implement actual LLM integration
        # This would typically use transformers, OpenAI API, or other LLM
        # For now, return a structured mock response
        return "LLM model not yet integrated. This would be the generated answer based on the context."
    
    def _generate_fallback_answer(self, query: str, search_results: List[SearchResult]) -> str:
        """Generate a fallback structured answer when LLM is not available"""
        if not search_results:
            return "No relevant information found."
        
        # Create a structured response
        answer_parts = [
            f"Based on the available documents, here's what I found regarding '{query}':"
        ]
        
        for i, result in enumerate(search_results[:3]):  # Limit to top 3 results
            snippet = result.content[:200] + "..." if len(result.content) > 200 else result.content
            confidence_text = "highly relevant" if result.score > 0.8 else "relevant" if result.score > 0.6 else "somewhat relevant"
            
            answer_parts.append(
                f"\n{i+1}. From {result.filename} ({confidence_text}, score: {result.score:.2f}):\n   {snippet}"
            )
        
        if len(search_results) > 3:
            answer_parts.append(f"\n...and {len(search_results) - 3} more relevant sources.")
        
        answer_parts.append("\nNote: This response is generated from document excerpts. For complete context, please refer to the original documents.")
        
        return "\n".join(answer_parts)
    
    async def semantic_search(
        self, 
        query: str, 
        tenant_id: UUID,
        max_results: int = 20,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Perform semantic search without answer generation
        
        Args:
            query: Search query
            tenant_id: Tenant ID for isolation
            max_results: Maximum number of results
            metadata_filters: Optional metadata filters
            
        Returns:
            List[SearchResult]: Ranked search results
        """
        query_embedding = await self._generate_query_embedding(query)
        
        return await self._search_relevant_chunks(
            query_embedding=query_embedding,
            tenant_id=tenant_id,
            max_results=max_results,
            metadata_filters=metadata_filters
        )
    
    async def get_document_chunks(
        self, 
        file_id: UUID, 
        tenant_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document"""
        result = await self.db.execute(
            select(EmbeddingChunk)
            .where(
                EmbeddingChunk.file_id == file_id,
                EmbeddingChunk.tenant_id == tenant_id
            )
            .order_by(EmbeddingChunk.chunk_index)
        )
        
        chunks = result.scalars().all()
        return [
            {
                'chunk_id': str(chunk.id),
                'chunk_index': chunk.chunk_index,
                'content': chunk.chunk_content,
                'token_count': chunk.token_count,
                'chunk_hash': chunk.chunk_hash,
                'processed_at': chunk.processed_at.isoformat(),
                'embedding_model': chunk.embedding_model
            }
            for chunk in chunks
        ]
    
    async def validate_query(self, query: str, tenant_id: UUID) -> Dict[str, Any]:
        """
        Validate a query and provide suggestions
        
        TODO: Implement query validation logic
        """
        return {
            'is_valid': len(query.strip()) > 0,
            'suggestions': [],
            'estimated_tokens': len(query.split()),
            'estimated_cost': 0.0
        }
    
    async def get_query_suggestions(
        self, 
        partial_query: str, 
        tenant_id: UUID,
        max_suggestions: int = 5
    ) -> List[str]:
        """
        Get query suggestions based on partial input
        
        TODO: Implement query suggestion logic
        """
        # Placeholder suggestions
        return [
            f"{partial_query} policy",
            f"{partial_query} process", 
            f"{partial_query} guidelines",
            f"{partial_query} requirements",
            f"{partial_query} overview"
        ][:max_suggestions]
    
    async def get_tenant_documents(
        self, 
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search_query: Optional[str] = None,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get documents for a tenant with optional search and filtering
        """
        files = await self.file_service.list_files(
            tenant_id=tenant_id,
            skip=(page - 1) * page_size,
            limit=page_size
        )
        
        documents = []
        for file in files:
            # Get chunk count for each file
            result = await self.db.execute(
                select(EmbeddingChunk)
                .where(EmbeddingChunk.file_id == file.id)
            )
            chunks = result.scalars().all()
            
            documents.append({
                'id': str(file.id),
                'filename': file.filename,
                'file_path': file.file_path,
                'file_size': file.file_size,
                'mime_type': file.mime_type,
                'sync_status': file.sync_status,
                'word_count': file.word_count,
                'page_count': file.page_count,
                'chunk_count': len(chunks),
                'created_at': file.created_at.isoformat(),
                'updated_at': file.updated_at.isoformat()
            })
        
        return {
            'documents': documents,
            'page': page,
            'page_size': page_size,
            'total_count': len(documents)  # TODO: Get actual total count
        }
    
    async def get_rag_statistics(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get RAG usage statistics for a tenant"""
        # TODO: Implement actual statistics collection
        return {
            'total_queries': 0,
            'total_documents': 0,
            'total_chunks': 0,
            'average_response_time': 0.0,
            'average_confidence': 0.0,
            'most_queried_topics': [],
            'query_success_rate': 0.0
        }
    
    async def create_query_feedback(
        self, 
        query_id: str, 
        rating: int, 
        feedback: Optional[str] = None,
        helpful: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Store query feedback for improvement
        
        TODO: Implement feedback storage
        """
        return {
            'success': True,
            'message': 'Feedback recorded successfully'
        }


# Dependency function for FastAPI
async def get_rag_service(
    db_session: AsyncSession,
    file_service: FileService
) -> RAGService:
    """Dependency to get RAG service with required dependencies"""
    service = RAGService(db_session, file_service)
    await service.initialize()
    return service