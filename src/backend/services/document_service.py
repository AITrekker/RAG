"""
Service layer for handling document-related business logic.
"""
import logging
from pathlib import Path
from sqlalchemy.orm import Session

from ..core.tenant_manager import TenantManager
from ..models.tenant import TenantDocument
from ..utils.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)

class DocumentService:
    """Encapsulates all logic for document management."""

    def __init__(
        self,
        db: Session,
        vector_manager: VectorStoreManager,
        tenant_id: str,
    ):
        if not tenant_id:
            raise ValueError("Tenant ID must be provided to DocumentService")
        self.db = db
        self.vector_manager = vector_manager
        self.tenant_id = tenant_id
        self.tenant_manager = TenantManager(db)

    def delete_document(self, document_id: str) -> None:
        """
        Deletes a single document and its associated data from all storage layers.

        Args:
            document_id: The ID of the document to delete.
        
        Raises:
            ValueError: If the document is not found.
        """
        logger.info(f"Service: Deleting document {document_id} for tenant {self.tenant_id}")
        
        document = self.db.query(TenantDocument).filter(
            TenantDocument.tenant_id == self.tenant_id,
            TenantDocument.document_id == document_id
        ).first()

        if not document:
            raise ValueError("Document not found")

        # 1. Delete from Vector Store
        try:
            collection = self.vector_manager.get_collection_for_tenant(self.tenant_id)
            collection.delete(where={"document_id": document_id})
            logger.info(f"Removed document {document_id} embeddings from vector store for tenant {self.tenant_id}")
        except Exception as e:
            logger.warning(f"Failed to remove embeddings from vector store for {document_id}: {e}")
            # Decide if this should be a critical failure or just a warning
            # For now, we'll log and continue

        # 2. Delete from Filesystem
        try:
            tenant_config = self.tenant_manager.get_tenant_configurations(self.tenant_id)
            if tenant_config and document.file_path:
                file_path = Path(document.file_path)
                if file_path.is_file():
                    file_path.unlink()
                    logger.info(f"Removed document file: {document.file_path}")
        except Exception as e:
            logger.warning(f"Failed to remove file from filesystem for {document_id}: {e}")

        # 3. Delete from Database
        self.db.delete(document)
        self.db.flush()
        logger.info(f"Document {document_id} deleted successfully from database for tenant {self.tenant_id}")

    def clear_all_documents(self) -> int:
        """
        Deletes ALL documents for the tenant from all storage layers.

        Returns:
            The number of documents deleted.
        """
        logger.warning(f"Service: Clearing ALL documents for tenant {self.tenant_id}")

        documents = self.db.query(TenantDocument).filter(
            TenantDocument.tenant_id == self.tenant_id
        ).all()
        
        doc_count = len(documents)
        if doc_count == 0:
            logger.info(f"No documents to clear for tenant {self.tenant_id}")
            return 0

        # 1. Clear from Vector Store
        try:
            self.vector_manager.cleanup_tenant_data(self.tenant_id)
            logger.info(f"Cleared all embeddings from vector store for tenant {self.tenant_id}")
        except Exception as e:
            logger.warning(f"Failed to clear embeddings from vector store for tenant {self.tenant_id}: {e}")

        # 2. Clear from Filesystem
        try:
            tenant_config = self.tenant_manager.get_tenant_configurations(self.tenant_id)
            if tenant_config:
                for document in documents:
                    if document.file_path:
                        file_path = Path(document.file_path)
                        if file_path.is_file():
                            file_path.unlink()
                logger.info(f"Removed {doc_count} document files from filesystem for tenant {self.tenant_id}")
        except Exception as e:
            logger.warning(f"Failed to remove files from filesystem for tenant {self.tenant_id}: {e}")

        # 3. Clear from Database
        deleted_rows = self.db.query(TenantDocument).filter(
            TenantDocument.tenant_id == self.tenant_id
        ).delete(synchronize_session=False)
        self.db.flush()
        logger.info(f"Cleared {deleted_rows} documents from database for tenant {self.tenant_id}")
        
        return deleted_rows 