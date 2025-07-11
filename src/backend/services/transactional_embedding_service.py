"""
DEPRECATED: Transactional Embedding Service - No Longer Needed

This module is deprecated and no longer needed with PostgreSQL + pgvector.
The dual-database transaction coordination is no longer required.

Use PgVectorEmbeddingService for all embedding operations.
"""

import warnings
import logging
from enum import Enum
from typing import List, Dict, Any, Optional

warnings.warn(
    "transactional_embedding_service is deprecated and no longer needed with pgvector. "
    "Use PgVectorEmbeddingService instead.", 
    DeprecationWarning, 
    stacklevel=2
)

logger = logging.getLogger(__name__)


class TransactionPhase(Enum):
    """DEPRECATED: Transaction phases no longer needed with pgvector."""
    PREPARE = "prepare"
    COMMIT = "commit" 
    ROLLBACK = "rollback"
    COMPLETED = "completed"


class TransactionalEmbeddingService:
    """
    DEPRECATED: No longer needed with unified PostgreSQL + pgvector architecture.
    
    This service was designed for coordinating transactions between PostgreSQL and Qdrant.
    With pgvector, all operations happen within PostgreSQL transactions.
    """

    def __init__(self, *args, **kwargs):
        """Initialize deprecated service."""
        logger.error("TransactionalEmbeddingService is deprecated and no longer functional.")
        raise NotImplementedError(
            "TransactionalEmbeddingService is deprecated. "
            "Use PgVectorEmbeddingService for unified PostgreSQL + pgvector operations."
        )

    async def store_with_transaction(self, *args, **kwargs):
        """DEPRECATED: Use PgVectorEmbeddingService.store_embeddings() instead."""
        raise NotImplementedError("Use PgVectorEmbeddingService.store_embeddings() instead")

    async def update_with_transaction(self, *args, **kwargs):
        """DEPRECATED: Use PgVectorEmbeddingService.store_embeddings() instead."""
        raise NotImplementedError("Use PgVectorEmbeddingService.store_embeddings() instead")

    async def delete_with_transaction(self, *args, **kwargs):
        """DEPRECATED: Use PgVectorEmbeddingService.delete_file_embeddings() instead."""
        raise NotImplementedError("Use PgVectorEmbeddingService.delete_file_embeddings() instead")


class EmbeddingTransaction:
    """DEPRECATED: No longer needed with pgvector."""
    def __init__(self, *args, **kwargs):
        logger.error("EmbeddingTransaction is deprecated.")
        raise NotImplementedError("EmbeddingTransaction is deprecated with pgvector.")


# Legacy functions for backwards compatibility
def create_transactional_embedding_service(*args, **kwargs):
    """DEPRECATED: Use PgVectorEmbeddingService instead."""
    logger.error("create_transactional_embedding_service is deprecated.")
    raise NotImplementedError("Use dependency injection for PgVectorEmbeddingService instead.")


def get_transactional_embedding_service(*args, **kwargs):
    """DEPRECATED: Use PgVectorEmbeddingService instead.""" 
    logger.error("get_transactional_embedding_service is deprecated.")
    raise NotImplementedError("Use dependency injection for PgVectorEmbeddingService instead.")