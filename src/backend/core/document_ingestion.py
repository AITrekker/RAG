"""
Document ingestion pipeline for the Enterprise RAG Platform.

This module provides a document ingestion pipeline with tenant isolation.
"""

import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .document_processor import DocumentProcessor, ChunkingConfig

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of document ingestion operation."""
    success: bool
    tenant_id: str
    processed_documents: List = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.processed_documents is None:
            self.processed_documents = []


class DocumentIngestionPipeline:
    """Document ingestion pipeline with tenant isolation."""
    
    def __init__(self, chunking_config: ChunkingConfig = None):
        """Initialize the document ingestion pipeline."""
        self.document_processor = DocumentProcessor(chunking_config)
        logger.info("Document ingestion pipeline initialized")
    
    def ingest_file(
        self,
        tenant_id: str,
        file_path: str,
        filename: str = None
    ) -> IngestionResult:
        """Ingest a single document file."""
        try:
            if not os.path.exists(file_path):
                return IngestionResult(
                    success=False,
                    tenant_id=tenant_id,
                    error_message=f"File not found: {file_path}"
                )
            
            result = self.document_processor.process_file(
                file_path=file_path,
                tenant_id=tenant_id,
                filename=filename
            )
            
            if not result.success:
                return IngestionResult(
                    success=False,
                    tenant_id=tenant_id,
                    error_message=result.error_message
                )
            
            return IngestionResult(
                success=True,
                tenant_id=tenant_id,
                processed_documents=[result.document]
            )
            
        except Exception as e:
            logger.error(f"Error ingesting file {file_path}: {e}")
            return IngestionResult(
                success=False,
                tenant_id=tenant_id,
                error_message=f"Ingestion error: {str(e)}"
            )
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions."""
        return self.document_processor.get_supported_extensions()


def create_default_ingestion_pipeline() -> DocumentIngestionPipeline:
    """Create ingestion pipeline with default configuration."""
    return DocumentIngestionPipeline(ChunkingConfig()) 