"""
Document management API endpoints for the Enterprise RAG Platform.

Handles document upload, listing, deletion, and metadata operations.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Security, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import uuid
import os
from datetime import datetime
from pathlib import Path

from ....db.session import get_db
from ....middleware.auth import get_current_tenant, require_authentication
from ....middleware.tenant_context import get_current_tenant_id
from ....core.document_ingestion import DocumentIngestionPipeline
from ....utils.tenant_filesystem import TenantFileSystemManager
from ....utils.vector_store import get_vector_store_manager
from ....models.api_models import (
    DocumentResponse, DocumentListResponse, DocumentUploadResponse,
    DocumentMetadata, DocumentUpdateRequest
)
from ..providers import get_document_service
from ....services.document_service import DocumentService

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency to get filesystem manager
def get_filesystem_manager() -> TenantFileSystemManager:
    """Dependency to get filesystem manager."""
    return TenantFileSystemManager()

# Dependency to get document ingestion pipeline
def get_ingestion_pipeline(
    tenant_id: str = Security(get_current_tenant),
    # db: Session = Depends(get_db) - This is no longer needed at the pipeline level
) -> DocumentIngestionPipeline:
    """Dependency to get document ingestion pipeline."""
    # The pipeline now gets the vector_store_manager from a global instance
    # And other managers are initialized within its constructor.
    # The `db` session is passed to the pipeline's methods, not its constructor.
    return DocumentIngestionPipeline(
        tenant_id=tenant_id,
        vector_store_manager=get_vector_store_manager()
    )


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Security(get_current_tenant),
    fs_manager: TenantFileSystemManager = Depends(get_filesystem_manager),
    ingestion_pipeline: DocumentIngestionPipeline = Depends(get_ingestion_pipeline)
):
    """
    Upload a document for processing and indexing.
    
    Accepts various file formats (PDF, DOCX, TXT, etc.) and processes them
    through the document ingestion pipeline.
    """
    try:
        logger.info(f"Uploading document '{file.filename}' for tenant {tenant_id}")
        
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )
        
        # Check file size (10MB limit)
        if file.size and file.size > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds 10MB limit"
            )
        
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Save file to tenant's upload directory
        file_path = await fs_manager.save_uploaded_file(
            tenant_id=tenant_id,
            file=file,
            document_id=document_id
        )
        
        # Process document through ingestion pipeline
        result = await ingestion_pipeline.process_document(
            file_path=file_path,
            document_id=document_id,
            filename=file.filename,
            content_type=file.content_type
        )
        
        return DocumentUploadResponse(
            document_id=document_id,
            filename=file.filename,
            status="processed",
            chunks_created=result.chunks_created,
            processing_time=result.processing_time,
            file_size=file.size or 0,
            upload_timestamp=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload document for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload and process document"
        )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    tenant_id: str = Security(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    List all documents for the current tenant.
    
    Returns paginated list of documents with optional search filtering.
    """
    try:
        logger.info(f"Listing documents for tenant {tenant_id}, page {page}")
        
        # Import the model here to avoid circular imports
        from ....models.tenant import TenantDocument
        
        # Build query
        query = db.query(TenantDocument).filter(TenantDocument.tenant_id == tenant_id)
        
        # Apply search filter if provided
        if search:
            search_term = f"%{search.lower()}%"
            query = query.filter(TenantDocument.filename.ilike(search_term))
        
        # Get total count for pagination
        total_count = query.count()
        
        # Apply pagination and get results
        documents = query.order_by(TenantDocument.created_at.desc())\
                        .offset((page - 1) * page_size)\
                        .limit(page_size)\
                        .all()
        
        # Convert to response model
        document_responses = []
        for doc in documents:
            document_responses.append(DocumentResponse(
                document_id=doc.document_id,
                filename=doc.filename,
                upload_timestamp=doc.created_at,
                file_size=doc.file_size_bytes,
                status=doc.status,
                chunks_count=doc.chunk_count,
                content_type=doc.mime_type,
                metadata={
                    "document_type": doc.document_type,
                    "file_hash": doc.file_hash,
                    "file_path": doc.file_path,
                    "embedding_model": doc.embedding_model,
                    "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
                    "error_message": doc.error_message
                }
            ))
        
        return DocumentListResponse(
            documents=document_responses,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Failed to list documents for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document list"
        )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    tenant_id: str = Security(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific document.
    
    Returns comprehensive document information including metadata and processing status.
    """
    try:
        logger.info(f"Retrieving document {document_id} for tenant {tenant_id}")
        
        # TODO: Implement actual document retrieval from database
        # For now, return mock data or 404
        
        if document_id.startswith("doc-"):
            return DocumentResponse(
                document_id=document_id,
                filename=f"document_{document_id}.pdf",
                upload_timestamp=datetime.utcnow(),
                file_size=2048,
                status="processed",
                chunks_count=15,
                content_type="application/pdf",
                metadata={"page_count": 8}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve document {document_id} for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document information"
        )


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    request: DocumentUpdateRequest,
    tenant_id: str = Security(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Update document metadata.
    
    Allows updating document metadata such as tags, description, etc.
    """
    try:
        logger.info(f"Updating document {document_id} for tenant {tenant_id}")
        
        # TODO: Implement actual document update in database
        
        return DocumentResponse(
            document_id=document_id,
            filename=f"updated_document_{document_id}.pdf",
            upload_timestamp=datetime.utcnow(),
            file_size=2048,
            status="processed",
            chunks_count=15,
            content_type="application/pdf",
            metadata=request.metadata or {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update document {document_id} for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document"
        )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    doc_service: DocumentService = Depends(get_document_service),
    tenant_id: str = Security(get_current_tenant)
):
    """
    Delete a document and its associated data.
    
    This endpoint is now a thin wrapper around the DocumentService.
    """
    try:
        doc_service.delete_document(document_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    except Exception as e:
        logger.error(f"API: Failed to delete document {document_id}: {e}")
        # Re-raising as a generic 500 error to avoid leaking implementation details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the document."
        )


@router.delete("/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_all_documents(
    doc_service: DocumentService = Depends(get_document_service),
    tenant_id: str = Security(get_current_tenant)
):
    """
    Delete all documents for the current tenant.
    
    This endpoint is now a thin wrapper around the DocumentService.
    """
    try:
        deleted_count = doc_service.clear_all_documents()
        logger.info(f"API: Cleared {deleted_count} documents successfully.")
    except Exception as e:
        logger.error(f"API: Failed to clear all documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while clearing documents."
        )


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    tenant_id: str = Security(get_current_tenant),
    fs_manager: TenantFileSystemManager = Depends(get_filesystem_manager)
):
    """
    Download the original document file.
    
    Returns the original uploaded file for download.
    """
    try:
        logger.info(f"Downloading document {document_id} for tenant {tenant_id}")
        
        # TODO: Implement actual file download
        # For now, return 404
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download document {document_id} for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download document"
        )


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: str,
    page: int = 1,
    page_size: int = 20,
    tenant_id: str = Security(get_current_tenant),
    db: Session = Depends(get_db)
):
    """
    Get chunks/segments of a specific document.
    
    Returns paginated list of document chunks with their embeddings metadata.
    """
    try:
        logger.info(f"Retrieving chunks for document {document_id}, tenant {tenant_id}")
        
        # TODO: Implement actual chunk retrieval from database
        # For now, return mock data
        
        mock_chunks = [
            {
                "chunk_id": f"chunk-{i}",
                "document_id": document_id,
                "chunk_index": i,
                "text": f"This is chunk {i} of the document...",
                "page_number": (i // 3) + 1,
                "start_char": i * 100,
                "end_char": (i + 1) * 100,
                "embedding_vector": None,  # Don't return actual vectors
                "metadata": {"chunk_type": "paragraph"}
            }
            for i in range(1, 16)
        ]
        
        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_chunks = mock_chunks[start_idx:end_idx]
        
        return {
            "chunks": paginated_chunks,
            "total_count": len(mock_chunks),
            "page": page,
            "page_size": page_size
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve chunks for document {document_id}, tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document chunks"
        ) 