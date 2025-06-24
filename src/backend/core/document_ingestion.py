"""
Document Ingestion Pipeline for the Enterprise RAG Platform using Qdrant.

This module orchestrates the document ingestion process, including processing,
chunking, embedding generation, and storage directly into the Qdrant vector store.
"""

import logging
import uuid
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any

from qdrant_client.http.models import PointStruct

from .document_processor import DocumentProcessor, create_default_processor
from .embedding_manager import EmbeddingManager, get_embedding_manager
from ..utils.vector_store import VectorStoreManager, get_vector_store_manager

logger = logging.getLogger(__name__)


class DocumentIngestionPipeline:
    """Orchestrates the document ingestion workflow with Qdrant."""

    def __init__(
        self,
        tenant_id: str,
        vector_store_manager: VectorStoreManager = None,
        document_processor: DocumentProcessor = None,
        embedding_manager: EmbeddingManager = None,
    ):
        if not tenant_id:
            raise ValueError("Tenant ID must be provided.")
            
        self.tenant_id = tenant_id
        self.vector_store_manager = vector_store_manager or get_vector_store_manager()
        self.document_processor = document_processor or create_default_processor()
        self.embedding_manager = embedding_manager or get_embedding_manager()
        logger.info(f"Initialized DocumentIngestionPipeline for tenant '{self.tenant_id}'")

    async def ingest_document(
        self,
        file_path: Path,
        document_id: Optional[str] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Processes, chunks, and embeds a single document, storing it in Qdrant.

        Args:
            file_path: The path to the document file.
            document_id: An optional existing ID for the document. This will be
                         used as the doc_id in the processed document.

        Returns:
            A tuple containing the document ID and a list of the created chunk metadata.
        """
        try:
            # The new processor is stateless and doesn't know about tenants.
            processed_doc = self.document_processor.process_file(file_path)

            # Use the provided document_id or the one from the processor.
            doc_id = document_id or processed_doc.doc_id

            chunk_texts = [chunk.text for chunk in processed_doc.chunks]
            
            embedding_result = await self.embedding_manager.process_async(
                texts=chunk_texts,
                tenant_id=self.tenant_id,
            )

            if not embedding_result.success or embedding_result.embeddings is None:
                raise RuntimeError(f"Failed to generate embeddings: {embedding_result.error}")

            embeddings = embedding_result.embeddings
            embedding_size = len(embeddings[0])

            if len(embeddings) != len(processed_doc.chunks):
                raise RuntimeError("Mismatch between the number of chunks and generated embeddings.")

            points_to_upsert = []
            chunk_metadatas = []
            for i, chunk in enumerate(processed_doc.chunks):
                # Start with the file-level metadata and add chunk-specific info
                payload = processed_doc.metadata.copy()
                payload.update({
                    "document_id": doc_id,
                    "tenant_id": self.tenant_id,
                    "content": chunk.text,
                    "chunk_index": i,
                })
                
                point = PointStruct(
                    id=chunk.id,  # Use the stable chunk ID from the processor
                    vector=embeddings[i].tolist(),
                    payload=payload
                )
                points_to_upsert.append(point)
                chunk_metadatas.append(payload)

            self.vector_store_manager.add_documents(
                tenant_id=self.tenant_id,
                points=points_to_upsert,
                embedding_size=embedding_size,
            )

            logger.info(f"Successfully ingested and embedded document '{file_path.name}' (ID: {doc_id}).")
            
            return doc_id, chunk_metadatas
            
        except Exception as e:
            logger.error(f"Failed to ingest document {file_path}: {e}", exc_info=True)
            raise

    def delete_document(self, document_id: str):
        """
        Deletes a document and all its associated chunks from Qdrant.

        Args:
            document_id: The ID of the document to delete.
        """
        logger.info(f"Attempting to delete document with ID: {document_id}")
        
        # In Qdrant, we delete points based on a filter.
        # This will delete all points (chunks) that have the specified document_id.
        self.vector_store_manager.client.delete(
            collection_name=f"tenant_{self.tenant_id}_documents",
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        ),
                    ]
                )
            ),
            wait=True,
        )
        
        logger.info(f"Successfully issued deletion for document ID: {document_id}")

    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions."""
        # This could be derived from the document processor's config in a future version.
        return [".pdf", ".docx", ".txt", ".md", ".html", ".htm"] 