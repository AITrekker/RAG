"""
Basic Document Ingestion Pipeline implementation.
"""

from typing import Dict, Any, List


class DocumentIngestionPipeline:
    """Basic document ingestion pipeline for demo purposes."""
    
    def __init__(self, embedding_service=None, vector_store_manager=None, tenant_id: str = "default"):
        self.embedding_service = embedding_service
        self.vector_store_manager = vector_store_manager
        self.tenant_id = tenant_id
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions."""
        return [".pdf", ".docx", ".txt", ".md", ".html", ".htm"]
    
    def ingest_file(self, tenant_id: str, file_path: str) -> Dict[str, Any]:
        """Ingest a single file."""
        return {
            "success": True,
            "document_id": "mock_doc_id",
            "chunks_created": 10,
            "processing_time": 2.5
        } 