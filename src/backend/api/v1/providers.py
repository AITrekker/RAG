"""
Dependency injection providers for services.
"""
from functools import lru_cache
from fastapi import Depends

from src.backend.core.delta_sync import DeltaSync
from src.backend.core.document_processor import DocumentProcessor
from src.backend.core.document_service import DocumentService
from src.backend.middleware.auth import require_authentication
from src.backend.utils.vector_store import get_vector_store_manager, VectorStoreManager


@lru_cache(maxsize=1)
def get_document_processor() -> DocumentProcessor:
    """
    FastAPI dependency to get a singleton DocumentProcessor instance.
    Uses lru_cache to ensure only one instance is created.
    """
    return DocumentProcessor()


def get_delta_sync(
    doc_processor: DocumentProcessor = Depends(get_document_processor),
) -> DeltaSync:
    """FastAPI dependency to get a DeltaSync instance."""
    return DeltaSync(document_processor=doc_processor)


def get_document_service(
    tenant_id: str = Depends(require_authentication),
    vector_manager: VectorStoreManager = Depends(get_vector_store_manager),
) -> DocumentService:
    """FastAPI dependency to get a DocumentService instance."""
    return DocumentService(tenant_id=tenant_id, vector_manager=vector_manager) 