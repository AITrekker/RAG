"""
DEPRECATED: RAG Pipeline - Legacy Qdrant Support

This module is deprecated and has been replaced with the RAGService using PostgreSQL + pgvector.
Use RAGService instead.

This wrapper exists for backwards compatibility only.
"""

import logging
import warnings
import time
from typing import List, Dict, Any, Optional

warnings.warn(
    "rag_pipeline module is deprecated. Use RAGService instead.", 
    DeprecationWarning, 
    stacklevel=2
)

# Legacy imports for compatibility
from ..utils.vector_store import get_vector_store_manager, VectorStoreManager

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    DEPRECATED: Legacy RAG pipeline.
    
    This class is deprecated and no longer functional.
    Use RAGService for RAG operations.
    """

    def __init__(self, embedding_service=None, llm_service=None, vector_manager: VectorStoreManager = None, tenant_id: str = None):
        """Initialize deprecated RAG pipeline."""
        logger.warning("RAGPipeline is deprecated. Use RAGService instead.")
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.vector_manager = vector_manager or get_vector_store_manager()
        self.tenant_id = tenant_id

    async def process_query(self, query: str, max_sources: int = 5) -> Dict[str, Any]:
        """
        DEPRECATED: Query processing moved to RAGService.
        
        Use RAGService.process_query() instead.
        """
        logger.error("process_query is deprecated. Use RAGService.process_query() instead.")
        raise NotImplementedError("Use RAGService.process_query() instead")

    async def _retrieve_context(self, query: str, tenant_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        DEPRECATED: Context retrieval moved to RAGService.
        
        Use RAGService._search_relevant_chunks() instead.
        """
        logger.error("_retrieve_context is deprecated. Use RAGService._search_relevant_chunks() instead.")
        raise NotImplementedError("Use RAGService._search_relevant_chunks() instead")

    async def _generate_answer(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """
        DEPRECATED: Answer generation moved to RAGService.
        
        Use RAGService._generate_answer() instead.
        """
        logger.error("_generate_answer is deprecated. Use RAGService._generate_answer() instead.")
        raise NotImplementedError("Use RAGService._generate_answer() instead")


# Legacy factory function for backwards compatibility
def create_rag_pipeline(tenant_id: str) -> RAGPipeline:
    """
    DEPRECATED: Create RAG pipeline.
    
    Use dependency injection to get RAGService instead.
    """
    logger.warning("create_rag_pipeline is deprecated. Use dependency injection for RAGService.")
    return RAGPipeline(tenant_id=tenant_id)


def get_rag_pipeline(tenant_id: str) -> RAGPipeline:
    """
    DEPRECATED: Get RAG pipeline.
    
    Use dependency injection to get RAGService instead.
    """
    logger.warning("get_rag_pipeline is deprecated. Use dependency injection for RAGService.")
    return RAGPipeline(tenant_id=tenant_id)