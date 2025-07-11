"""
DEPRECATED: Document Service - Legacy Qdrant Support

This module is deprecated and has been replaced with PostgreSQL + pgvector services.
Use FileService and PgVectorEmbeddingService instead.

This wrapper exists for backwards compatibility only.
"""

import logging
import warnings
from pathlib import Path

warnings.warn(
    "document_service module is deprecated. Use FileService and PgVectorEmbeddingService instead.", 
    DeprecationWarning, 
    stacklevel=2
)

from ..utils.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)


class DocumentService:
    """
    DEPRECATED: Legacy document service.
    
    This class is deprecated and no longer functional.
    Use FileService and PgVectorEmbeddingService for document operations.
    """

    def __init__(self, vector_manager: VectorStoreManager, tenant_id: str):
        """Initialize deprecated document service."""
        logger.warning("DocumentService is deprecated. Use FileService and PgVectorEmbeddingService instead.")
        if not tenant_id:
            raise ValueError("Tenant ID must be provided to DocumentService")
        self.vector_manager = vector_manager
        self.tenant_id = tenant_id

    def delete_document(self, document_id: str) -> None:
        """
        DEPRECATED: Document deletion moved to FileService.
        
        Use FileService.delete_file() and PgVectorEmbeddingService.delete_file_embeddings() instead.
        """
        logger.error("delete_document is deprecated. Use FileService.delete_file() instead.")
        raise NotImplementedError("Use FileService.delete_file() and PgVectorEmbeddingService.delete_file_embeddings() instead")

    def get_document(self, document_id: str):
        """
        DEPRECATED: Document retrieval moved to FileService.
        
        Use FileService.get_file() instead.
        """
        logger.error("get_document is deprecated. Use FileService.get_file() instead.")
        raise NotImplementedError("Use FileService.get_file() instead")

    def list_documents(self):
        """
        DEPRECATED: Document listing moved to FileService.
        
        Use FileService.list_files() instead.
        """
        logger.error("list_documents is deprecated. Use FileService.list_files() instead.")
        raise NotImplementedError("Use FileService.list_files() instead")


# Legacy factory function for backwards compatibility
def create_document_service(vector_manager: VectorStoreManager, tenant_id: str) -> DocumentService:
    """
    DEPRECATED: Create document service.
    
    Use dependency injection to get FileService and PgVectorEmbeddingService instead.
    """
    logger.warning("create_document_service is deprecated. Use dependency injection for FileService and PgVectorEmbeddingService.")
    return DocumentService(vector_manager, tenant_id)