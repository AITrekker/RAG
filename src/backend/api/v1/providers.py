"""
Dependency injection providers for services.
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from ...db.session import get_db
from ...services.document_service import DocumentService
from ...middleware.tenant_context import get_current_tenant_id
from ...utils.vector_store import get_vector_store_manager, VectorStoreManager


def get_document_service(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    vector_manager: VectorStoreManager = Depends(get_vector_store_manager)
) -> DocumentService:
    """FastAPI dependency to get a DocumentService instance."""
    return DocumentService(
        db=db, 
        tenant_id=tenant_id, 
        vector_manager=vector_manager
    ) 