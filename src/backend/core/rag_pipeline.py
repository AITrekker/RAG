"""
Core RAG (Retrieval-Augmented Generation) Pipeline for the Enterprise Platform.

This module orchestrates the end-to-end process of handling a user query,
retrieving relevant context from documents, and generating a coherent,
cited answer using a Large Language Model.
"""

import logging
import time
from typing import List, Dict, Any, Optional

from .embeddings import get_embedding_service, EmbeddingService
from .llm_service import get_llm_service, LLMService
from ..utils.vector_store import get_vector_store_manager, VectorStoreManager
from ..models.api_models import RAGResponse, RAGSource

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    The main pipeline for processing RAG queries. It integrates embedding,
    vector search, and language model generation to produce answers with citations.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        llm_service: LLMService,
        vector_store_manager: VectorStoreManager,
    ):
        """
        Initializes the RAG pipeline with necessary service components.
        """
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.vector_store_manager = vector_store_manager
        logger.info("RAGPipeline initialized successfully.")

    async def process_query(self, query: str, tenant_id: str) -> RAGResponse:
        """
        Processes a user query through the full RAG pipeline.

        Args:
            query: The user's question.
            tenant_id: The ID of the tenant making the request.

        Returns:
            A RAGResponse object containing the answer, sources, and metadata.
        """
        start_time = time.time()
        logger.info(f"Processing query for tenant '{tenant_id}': '{query}'")

        try:
            retrieved_chunks = await self._retrieve_context(query, tenant_id)
            if not retrieved_chunks:
                logger.warning(f"No relevant context found for query: '{query}'")
                processing_time = time.time() - start_time
                return RAGResponse(
                    answer="I could not find any relevant information in your documents to answer this question.",
                    sources=[],
                    query=query,
                    confidence=0.0,
                    processing_time=processing_time,
                    llm_metadata=None
                )
        except Exception as e:
            logger.error(f"Error during context retrieval for tenant '{tenant_id}': {e}", exc_info=True)
            raise RuntimeError("Failed to retrieve document context.") from e

        try:
            context_str = "\n".join([chunk['text'] for chunk in retrieved_chunks])
            llm_response = self.llm_service.generate_response(query, context_str)
        except Exception as e:
            logger.error(f"Error during LLM generation for tenant '{tenant_id}': {e}", exc_info=True)
            raise RuntimeError("Failed to generate a response from the language model.") from e
        
        processing_time = time.time() - start_time
        logger.info(f"Successfully processed query in {processing_time:.2f} seconds.")

        return RAGResponse(
            answer=llm_response.text,
            sources=[RAGSource(**chunk) for chunk in retrieved_chunks],
            query=query,
            confidence=self._calculate_confidence(retrieved_chunks),
            processing_time=processing_time,
            llm_metadata={
                "model_name": llm_response.model_name,
                "total_tokens": llm_response.total_tokens
            }
        )

    async def _retrieve_context(self, query: str, tenant_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves the most relevant document chunks for a given query from Qdrant.

        Args:
            query: The user's question.
            tenant_id: The ID of the tenant.
            top_k: The number of chunks to retrieve.

        Returns:
            A list of retrieved chunks, each as a dictionary.
        """
        logger.info(f"Generating embedding for query: '{query}'")
        query_embedding_result = self.embedding_service.encode_texts([query])
        
        if not query_embedding_result.success or not query_embedding_result.embeddings:
            logger.error("Failed to generate query embedding.")
            return []
            
        query_embedding = query_embedding_result.embeddings[0]

        logger.info(f"Searching vector store for tenant '{tenant_id}'...")
        
        search_results = self.vector_store_manager.similarity_search(
            tenant_id=tenant_id,
            query_embedding=query_embedding,
            top_k=top_k
        )
        
        retrieved_chunks = []
        if search_results:
            for point in search_results:
                payload = point.payload or {}
                chunk_data = {
                    "id": point.id,
                    "text": payload.get("content", ""),
                    "score": point.score,
                    "source": payload.get("source"),
                    "page_number": payload.get("page_number"),
                    "document_id": payload.get("document_id"),
                }
                retrieved_chunks.append(chunk_data)

        logger.info(f"Retrieved {len(retrieved_chunks)} chunks from vector store.")
        return retrieved_chunks
    
    def _calculate_confidence(self, chunks: List[Dict[str, Any]]) -> float:
        """Calculates a simple confidence score based on retrieval scores."""
        if not chunks:
            return 0.0
        
        avg_score = sum(chunk.get('score', 0.0) for chunk in chunks) / len(chunks)
        return round(avg_score, 2)


# Singleton instance management
_rag_pipeline_instance: Optional[RAGPipeline] = None

def get_rag_pipeline() -> RAGPipeline:
    """
    Returns a singleton instance of the RAGPipeline.
    This ensures that all services are initialized only once.
    """
    global _rag_pipeline_instance
    if _rag_pipeline_instance is None:
        logger.info("Initializing singleton RAGPipeline instance.")
        _rag_pipeline_instance = RAGPipeline(
            embedding_service=get_embedding_service(),
            llm_service=get_llm_service(),
            vector_store_manager=get_vector_store_manager(),
        )
    return _rag_pipeline_instance
