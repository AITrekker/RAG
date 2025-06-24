"""
Document management API endpoints for the Enterprise RAG Platform.

Handles document upload, listing, and deletion using a Qdrant-based backend.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from typing import List
import logging
import tempfile
import os
from pathlib import Path
import shutil

from src.backend.middleware.auth import require_authentication
from src.backend.services.document_service import DocumentService
from src.backend.models.api_models import (
    DocumentListResponse, DocumentUploadResponse, DocumentResponse
)
from src.backend.api.v1.providers import get_document_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Depends(require_authentication)
):
    """
    Accepts a document upload and places it in the tenant's directory for asynchronous processing.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty.")

    try:
        # Define the path to the tenant's upload directory
        # This path should be consistent with what DeltaSync scans
        tenant_uploads_path = Path(f"data/tenants/{tenant_id}/uploads")
        tenant_uploads_path.mkdir(parents=True, exist_ok=True)
        
        # Save the file
        file_path = tenant_uploads_path / file.filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"Successfully saved uploaded file to {file_path} for tenant {tenant_id}")

        return DocumentUploadResponse(
            filename=file.filename,
            status="accepted_for_processing"
        )
    except Exception as e:
        logger.error(f"Failed to upload document for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save document for processing: {e}"
        )

@router.get("/", response_model=DocumentListResponse, dependencies=[Depends(require_authentication)])
async def list_documents(
    tenant_id: str = Depends(require_authentication),
):
    """
    Lists all documents for the current tenant.
    """
    # This logic needs to be implemented in DocumentService
    return DocumentListResponse(documents=[], total_count=0)


@router.get("/{document_id}", response_model=DocumentResponse, dependencies=[Depends(require_authentication)])
async def get_document(
    document_id: str,
    tenant_id: str = Depends(require_authentication),
):
    """
    Gets metadata for a specific document.
    """
    # This logic needs to be implemented in DocumentService
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_authentication)])
async def delete_document(
    document_id: str,
    tenant_id: str = Depends(require_authentication),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Deletes a document.
    """
    try:
        document_service.delete_document(document_id)
    except ValueError as e:
        # This occurs if the document_id is not found
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting document {document_id} for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete document.") 