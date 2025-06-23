"""
Document Ingestion Pipeline for the Enterprise RAG Platform.

This module orchestrates the entire document ingestion process, including
file monitoring, version control, processing, chunking, embedding generation,
and storage in both a metadata database and a vector store.
"""

import logging
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
from sqlalchemy.orm import Session

from .document_processor import DocumentProcessor, create_default_processor
from .embedding_manager import EmbeddingManager, get_embedding_manager
from ..models.document import Document
from ..utils.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)


class DocumentIngestionPipeline:
    """Orchestrates the document ingestion workflow."""

    def __init__(
        self,
        tenant_id: str,
        vector_store_manager: VectorStoreManager,
        document_processor: DocumentProcessor = None,
        embedding_manager: EmbeddingManager = None,
    ):
        # Import here to avoid circular imports
        from ..core.tenant_manager import get_tenant_manager
        from ..db.session import get_db
        
        self.tenant_id_string = tenant_id  # Keep original string for logging
        
        # Resolve tenant_id to UUID
        db = next(get_db())
        tenant_manager = get_tenant_manager(db)
        tenant_uuid = tenant_manager.get_tenant_uuid(tenant_id)
        
        if not tenant_uuid:
            raise ValueError(f"Tenant not found: {tenant_id}")
        
        self.tenant_id = tenant_uuid  # Use UUID for database operations
        self.vector_store_manager = vector_store_manager
        self.document_processor = document_processor or create_default_processor()
        # Create embedding manager with auto_persist disabled since we handle vector store operations manually
        self.embedding_manager = embedding_manager or get_embedding_manager(auto_persist=False)
        logger.info(f"Initialized DocumentIngestionPipeline for tenant '{self.tenant_id_string}' (UUID: {self.tenant_id})")

    async def ingest_document(
        self, 
        db: Session, 
        file_path: Path, 
        force_reingest: bool = False
    ) -> Tuple[Optional[Document], List[Dict[str, Any]]]:
        """
        Processes, chunks, and embeds a single document, handling versioning.

        If the document is unchanged and force_reingest is False, it will be skipped.

        Args:
            db: The database session.
            file_path: The path to the document file.
            force_reingest: If True, process the document even if its hash is unchanged.

        Returns:
            A tuple of the new Document object (or the existing one if skipped)
            and a list of created chunk dictionaries.
        """
        try:
            file_hash = self.document_processor._calculate_file_hash(str(file_path))

            # Find the current version of the document by filename
            previous_version = db.query(Document).filter(
                Document.tenant_id == self.tenant_id,
                Document.filename == file_path.name,
                Document.is_current_version == True
            ).first()

            # --- Versioning and Skip Logic ---
            if not force_reingest and previous_version and previous_version.file_hash == file_hash:
                logger.info(f"Document '{file_path.name}' is unchanged and not forced. Skipping ingestion.")
                # Return the existing document and no new chunks
                return previous_version, []
            
            if previous_version:
                 logger.info(f"Document '{file_path.name}' has been modified or re-ingestion is forced.")
            else:
                logger.info(f"Document '{file_path.name}' is new.")

            # --- Processing ---
            processing_result = self.document_processor.process_file(
                file_path=str(file_path),
                tenant_id=self.tenant_id_string,
                filename=file_path.name
            )

            if not processing_result.success:
                raise RuntimeError(f"Failed to process file: {processing_result.error_message}")

            new_document = processing_result.document
            chunks = processing_result.chunks

            # --- Versioning Update ---
            if previous_version:
                logger.info(f"Creating new version for document '{new_document.filename}'. Old version becomes inactive.")
                previous_version.is_current_version = False
                db.add(previous_version)
                new_document.version = previous_version.version + 1
                new_document.parent_document_id = previous_version.id
            else:
                new_document.version = 1
            
            db.add(new_document)
            
            # Flush to get the document ID assigned
            db.flush()

            # Generate embeddings for the chunks
            chunk_contents = [chunk.content for chunk in chunks]
            
            embedding_result = await self.embedding_manager.process_async(
                texts=chunk_contents,
                tenant_id=self.tenant_id_string,
            )

            if not embedding_result.success or embedding_result.embeddings is None:
                raise RuntimeError(f"Failed to generate embeddings: {embedding_result.error}")

            embeddings = embedding_result.embeddings

            if len(embeddings) != len(chunks):
                raise RuntimeError("Mismatch between number of chunks and generated embeddings.")

            # Update chunks with embeddings and add to DB
            for i, chunk in enumerate(chunks):
                # Convert numpy array to list for JSON serialization
                chunk.embedding_vector = embeddings[i].tolist() if hasattr(embeddings[i], 'tolist') else embeddings[i]
                chunk.document_id = new_document.id
                db.add(chunk)

            # Flush to get chunk IDs assigned
            db.flush()

            # Add chunks to the vector store
            try:
                collection = self.vector_store_manager.get_collection_for_tenant(self.tenant_id_string)
                
                # Convert embeddings back to list format for ChromaDB
                embeddings_for_chroma = []
                for chunk in chunks:
                    if isinstance(chunk.embedding_vector, list):
                        embeddings_for_chroma.append(chunk.embedding_vector)
                    else:
                        # Handle case where it might still be a numpy array
                        embeddings_for_chroma.append(chunk.embedding_vector.tolist() if hasattr(chunk.embedding_vector, 'tolist') else chunk.embedding_vector)
                
                collection.add(
                    ids=[str(chunk.id) for chunk in chunks],
                    embeddings=embeddings_for_chroma,
                    documents=[chunk.content for chunk in chunks],
                    metadatas=[chunk.to_dict() for chunk in chunks]
                )
                logger.info(f"Added {len(chunks)} chunks to vector store for tenant '{self.tenant_id_string}'.")
            except Exception as e:
                logger.error(f"Failed to add chunks to vector store for tenant '{self.tenant_id_string}': {e}", exc_info=True)
                # Don't rollback here, let the caller decide
                raise RuntimeError("Failed to update vector store.") from e

            # Commit all database changes for this document at once
            db.commit()
            
            # Refresh objects to get updated state
            db.refresh(new_document)
            for chunk in chunks:
                db.refresh(chunk)
                
            logger.info(f"Successfully ingested and embedded document '{new_document.filename}' (v{new_document.version}).")
            
            return new_document, [chunk.to_dict() for chunk in chunks]
            
        except Exception as e:
            # Rollback the transaction for this document only
            db.rollback()
            logger.error(f"Failed to ingest document {file_path}: {e}", exc_info=True)
            raise

    def delete_document(self, db: Session, document_id: int):
        """
        Deletes a document and all its associated data.

        Args:
            db: The database session.
            document_id: The ID of the document to delete.
        """
        logger.info(f"Attempting to delete document with ID: {document_id}")
        
        doc_to_delete = db.query(Document).filter(Document.id == document_id).first()

        if not doc_to_delete:
            logger.warning(f"Document with ID {document_id} not found for deletion.")
            return

        # 1. Get all chunk IDs before deleting them
        chunk_ids_to_delete = [str(chunk.id) for chunk in doc_to_delete.chunks]

        # 2. Delete from Vector Store
        if chunk_ids_to_delete:
            try:
                collection = self.vector_store_manager.get_collection_for_tenant(self.tenant_id_string)
                collection.delete(ids=chunk_ids_to_delete)
                logger.info(f"Deleted {len(chunk_ids_to_delete)} chunks from vector store for document {document_id}.")
            except Exception as e:
                logger.error(f"Failed to delete chunks from vector store for document {document_id}: {e}", exc_info=True)
                # We might want to raise an exception here to halt the process
                # For now, we'll log and continue with DB deletion.

        # 3. Delete from Database (cascading delete should handle chunks)
        # Note: This assumes the database is configured with cascading deletes
        # from Document to Chunk. If not, chunks must be deleted manually.
        db.delete(doc_to_delete)
        db.commit()
        
        logger.info(f"Successfully deleted document {doc_to_delete.filename} (ID: {document_id}) from database.")

    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions."""
        return [".pdf", ".docx", ".txt", ".md", ".html", ".htm"] 