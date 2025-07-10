"""
Service layer for handling document-related business logic.
"""
import logging
from pathlib import Path
# from sqlalchemy.orm import Session

from ..utils.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)

class DocumentService:
    """Encapsulates all logic for document management."""

    def __init__(
        self,
        vector_manager: VectorStoreManager,
        tenant_id: str,
    ):
        if not tenant_id:
            raise ValueError("Tenant ID must be provided to DocumentService")
        self.vector_manager = vector_manager
        self.tenant_id = tenant_id

    def delete_document(self, document_id: str) -> None:
        """
        Deletes a single document and its associated data from all storage layers.
        It now uses Qdrant as the source of truth for metadata.

        Args:
            document_id: The ID of the document (which is the point ID of one of its chunks) to delete.
        
        Raises:
            ValueError: If the document is not found.
        """
        logger.info(f"Service: Deleting document {document_id} for tenant {self.tenant_id}")
        
        # 1. Fetch metadata from Qdrant to find the file path
        try:
            points = self.vector_manager.client.retrieve(
                collection_name=self.vector_manager.get_collection_name(),
                ids=[document_id],
                with_payload=True
            )
            if not points:
                raise ValueError("Document chunk not found in vector store")

            file_path_str = points[0].payload.get("metadata", {}).get("file_path")
            if not file_path_str:
                 logger.warning(f"No file_path in metadata for point {document_id}, cannot delete from filesystem.")
                 # Continue to delete from vector store
            else:
                # 2. Delete from Filesystem
                try:
                    file_path = Path(file_path_str)
                    if file_path.is_file():
                        file_path.unlink()
                        logger.info(f"Removed document file: {file_path_str}")
                except Exception as e:
                    logger.warning(f"Failed to remove file from filesystem for {document_id}: {e}")

            # 3. Delete all points associated with that file from Vector Store
            self.vector_manager.delete_documents_by_path(self.tenant_id, file_path_str)

        except Exception as e:
            logger.error(f"Failed to delete document {document_id} for tenant {self.tenant_id}: {e}", exc_info=True)
            raise

    def clear_all_documents(self) -> int:
        """
        Deletes ALL documents for the tenant from all storage layers.

        Returns:
            The number of documents deleted (approximated by files).
        """
        logger.warning(f"Service: Clearing ALL documents for tenant {self.tenant_id}")
        collection_name = self.vector_manager.get_collection_name()
        deleted_files = 0

        try:
            # 1. Scroll through all documents to get their file paths for deletion
            all_points, _ = self.vector_manager.client.scroll(
                collection_name=collection_name, limit=10000, with_payload=True, with_vectors=False
            )
            
            unique_files_to_delete = {p.payload.get("metadata", {}).get("file_path") for p in all_points}

            # 2. Clear from Filesystem
            for file_path_str in unique_files_to_delete:
                if file_path_str:
                    try:
                        file_path = Path(file_path_str)
                        if file_path.is_file():
                            file_path.unlink()
                            deleted_files += 1
                    except Exception as e:
                        logger.warning(f"Failed to remove file from filesystem: {file_path_str}: {e}")
            logger.info(f"Removed {deleted_files} document files from filesystem for tenant {self.tenant_id}")
            
            # 3. Clear from Vector Store by deleting all tenant points
            # Since we use environment collections, we can't delete the whole collection
            # Instead, we delete all points for this tenant using a filter
            all_point_ids = [p.id for p in all_points]
            if all_point_ids:
                self.vector_manager.delete_documents(self.tenant_id, all_point_ids)
                logger.info(f"Cleared {len(all_point_ids)} embeddings for tenant {self.tenant_id}")

        except Exception as e:
            logger.error(f"Failed to clear documents for tenant {self.tenant_id}: {e}", exc_info=True)
            # If the collection doesn't exist, that's fine.
            if "not found" not in str(e).lower():
                raise

        return deleted_files 