"""
DEPRECATED: Vector Store Management - Legacy Qdrant Support

This module is deprecated and has been replaced with PostgreSQL + pgvector.
Use PgVectorEmbeddingService instead.

This wrapper exists for backwards compatibility only.
"""

import logging
import warnings
from typing import Optional, List, Dict, Any

warnings.warn(
    "vector_store module is deprecated. Use PgVectorEmbeddingService instead.", 
    DeprecationWarning, 
    stacklevel=2
)

logger = logging.getLogger(__name__)

# Environment configuration for compatibility
CURRENT_ENVIRONMENT = "development"
VALID_ENVIRONMENTS = ["production", "staging", "test", "development"]


class VectorStoreManager:
    """
    DEPRECATED: Legacy vector store manager.
    
    This class is deprecated and no longer functional.
    Use PgVectorEmbeddingService for vector operations.
    """

    def __init__(self, *args, **kwargs):
        """Initialize deprecated vector store manager."""
        logger.warning("VectorStoreManager is deprecated. Use PgVectorEmbeddingService instead.")
        self.environment = CURRENT_ENVIRONMENT
        self.client = None

    def get_collection_name(self, environment: str = None) -> str:
        """Get collection name for compatibility."""
        env = environment or self.environment
        return f"documents_{env}"

    def get_collection_for_environment(self, embedding_size: int, environment: str = None):
        """Deprecated: Collection management moved to PostgreSQL."""
        logger.warning("Collection management moved to PostgreSQL with pgvector")
        return None

    def add_points(self, tenant_id: str, points: List[Dict], embedding_size: int, environment: str = None):
        """Deprecated: Point management moved to PostgreSQL."""
        logger.error("add_points is deprecated. Use PgVectorEmbeddingService.store_embeddings() instead.")
        raise NotImplementedError("Use PgVectorEmbeddingService.store_embeddings() instead")

    def search_points(self, tenant_id: str, query_embedding: List[float], top_k: int = 5, 
                     filter_metadata: Optional[Dict] = None, environment: str = None):
        """Deprecated: Search moved to PostgreSQL."""
        logger.error("search_points is deprecated. Use PgVectorEmbeddingService.search_similar_chunks() instead.")
        raise NotImplementedError("Use PgVectorEmbeddingService.search_similar_chunks() instead")

    def delete_points(self, tenant_id: str, point_ids: List[str], environment: str = None):
        """Deprecated: Deletion moved to PostgreSQL."""
        logger.error("delete_points is deprecated. Use PgVectorEmbeddingService.delete_file_embeddings() instead.")
        raise NotImplementedError("Use PgVectorEmbeddingService.delete_file_embeddings() instead")

    def get_points(self, tenant_id: str, point_ids: List[str], environment: str = None):
        """Deprecated: Point retrieval moved to PostgreSQL."""
        logger.error("get_points is deprecated. Query PostgreSQL embedding_chunks table instead.")
        raise NotImplementedError("Query PostgreSQL embedding_chunks table instead")


def get_vector_store_manager(environment: str = None) -> VectorStoreManager:
    """
    DEPRECATED: Get vector store manager.
    
    Returns a deprecated wrapper for backwards compatibility.
    Use PgVectorEmbeddingService instead.
    """
    logger.warning("get_vector_store_manager is deprecated. Use dependency injection to get PgVectorEmbeddingService.")
    return VectorStoreManager()


# Legacy function for backwards compatibility
def create_collection_if_not_exists(client, collection_name: str, embedding_size: int):
    """Deprecated: Collection creation moved to PostgreSQL."""
    logger.warning("create_collection_if_not_exists is deprecated. PostgreSQL tables are created automatically.")
    pass