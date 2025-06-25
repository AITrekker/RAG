"""
Document synchronization API endpoints.

This module provides per-tenant endpoints for:
- Triggering document sync operations
- Managing sync configuration
- Viewing sync history and status
- Document management

All endpoints are scoped to the authenticated tenant.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from typing import List, Optional
from datetime import datetime
import uuid

from ...models.api_models import (
    SyncTriggerRequest,
    SyncResponse,
    SyncHistoryResponse,
    SyncConfigRequest,
    SyncConfigResponse,
    DocumentResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    ErrorResponse
)
from ...core.delta_sync import DeltaSync
from ...core.document_service import DocumentService
from ...core.embedding_manager import EmbeddingManager
from ...middleware.auth import get_current_tenant
from ...config.settings import get_settings

router = APIRouter(prefix="/sync", tags=["Document Sync"])

# =============================================================================
# SYNC OPERATIONS
# =============================================================================

@router.post("/trigger", response_model=SyncResponse)
async def trigger_sync(
    request: SyncTriggerRequest,
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Trigger a document synchronization operation.
    
    Args:
        request: Sync trigger details
        current_tenant: Current tenant (from auth)
        
    Returns:
        SyncResponse: Sync operation details
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        sync_id = str(uuid.uuid4())
        
        # Create sync response
        sync_response = SyncResponse(
            sync_id=sync_id,
            tenant_id=tenant_id,
            status="pending",
            started_at=datetime.utcnow(),
            progress={"message": "Sync queued"}
        )
        
        # Start sync operation (async)
        delta_sync = DeltaSync(tenant_id=tenant_id)
        await delta_sync.start_sync(
            sync_id=sync_id,
            force_full_sync=request.force_full_sync,
            document_paths=request.document_paths
        )
        
        return sync_response
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger sync: {str(e)}"
        )

@router.get("/status/{sync_id}", response_model=SyncResponse)
async def get_sync_status(
    sync_id: str,
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Get the status of a specific sync operation.
    
    Args:
        sync_id: Sync operation ID
        current_tenant: Current tenant (from auth)
        
    Returns:
        SyncResponse: Sync operation status
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Get sync status from delta sync
        delta_sync = DeltaSync(tenant_id=tenant_id)
        sync_status = await delta_sync.get_sync_status(sync_id)
        
        if not sync_status:
            raise HTTPException(status_code=404, detail="Sync operation not found")
            
        return sync_status
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sync status: {str(e)}"
        )

@router.get("/history", response_model=SyncHistoryResponse)
async def get_sync_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Get sync operation history for the current tenant.
    
    Args:
        page: Page number for pagination
        page_size: Number of syncs per page
        current_tenant: Current tenant (from auth)
        
    Returns:
        SyncHistoryResponse: Sync history with pagination
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Get sync history
        delta_sync = DeltaSync(tenant_id=tenant_id)
        syncs = await delta_sync.get_sync_history(page=page, page_size=page_size)
        
        return SyncHistoryResponse(
            syncs=syncs,
            total_count=len(syncs)  # This should be total count, not page count
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sync history: {str(e)}"
        )

@router.post("/cancel/{sync_id}")
async def cancel_sync(
    sync_id: str,
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Cancel a running sync operation.
    
    Args:
        sync_id: Sync operation ID
        current_tenant: Current tenant (from auth)
        
    Returns:
        dict: Cancellation confirmation
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Cancel sync operation
        delta_sync = DeltaSync(tenant_id=tenant_id)
        success = await delta_sync.cancel_sync(sync_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Sync operation not found or not cancellable")
            
        return {"message": f"Sync {sync_id} cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel sync: {str(e)}"
        )

# =============================================================================
# SYNC CONFIGURATION
# =============================================================================

@router.get("/config", response_model=SyncConfigResponse)
async def get_sync_config(
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Get current sync configuration for the tenant.
    
    Args:
        current_tenant: Current tenant (from auth)
        
    Returns:
        SyncConfigResponse: Current sync configuration
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Get sync configuration
        delta_sync = DeltaSync(tenant_id=tenant_id)
        config = await delta_sync.get_sync_config()
        
        return config
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sync config: {str(e)}"
        )

@router.put("/config", response_model=SyncConfigResponse)
async def update_sync_config(
    request: SyncConfigRequest,
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Update sync configuration for the tenant.
    
    Args:
        request: New sync configuration
        current_tenant: Current tenant (from auth)
        
    Returns:
        SyncConfigResponse: Updated sync configuration
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Update sync configuration
        delta_sync = DeltaSync(tenant_id=tenant_id)
        updated_config = await delta_sync.update_sync_config(
            auto_sync=request.auto_sync,
            sync_interval=request.sync_interval,
            document_paths=request.document_paths,
            file_types=request.file_types,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap
        )
        
        return updated_config
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update sync config: {str(e)}"
        )

# =============================================================================
# DOCUMENT MANAGEMENT
# =============================================================================

@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Upload a document for processing.
    
    Args:
        file: Document file to upload
        current_tenant: Current tenant (from auth)
        
    Returns:
        DocumentUploadResponse: Upload result
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Validate file type
        settings = get_settings()
        if file.content_type not in settings.supported_file_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}"
            )
        
        # Upload and process document
        document_service = DocumentService(tenant_id=tenant_id)
        result = await document_service.upload_document(file)
        
        return DocumentUploadResponse(
            document_id=result["document_id"],
            name=result["name"],
            status=result["status"],
            message=result["message"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload document: {str(e)}"
        )

@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    List documents for the current tenant.
    
    Args:
        page: Page number for pagination
        page_size: Number of documents per page
        current_tenant: Current tenant (from auth)
        
    Returns:
        DocumentListResponse: List of documents with pagination
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Get documents
        document_service = DocumentService(tenant_id=tenant_id)
        documents = await document_service.list_documents(page=page, page_size=page_size)
        
        return documents
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list documents: {str(e)}"
        )

@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Get document details.
    
    Args:
        document_id: Document ID
        current_tenant: Current tenant (from auth)
        
    Returns:
        DocumentResponse: Document information
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Get document
        document_service = DocumentService(tenant_id=tenant_id)
        document = await document_service.get_document(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
            
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get document: {str(e)}"
        )

@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Delete a document.
    
    Args:
        document_id: Document ID
        current_tenant: Current tenant (from auth)
        
    Returns:
        dict: Deletion confirmation
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Delete document
        document_service = DocumentService(tenant_id=tenant_id)
        success = await document_service.delete_document(document_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
            
        return {"message": f"Document {document_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )

# =============================================================================
# SYNC STATISTICS
# =============================================================================

@router.get("/stats")
async def get_sync_stats(
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Get sync statistics for the current tenant.
    
    Args:
        current_tenant: Current tenant (from auth)
        
    Returns:
        dict: Sync statistics
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Get sync statistics
        delta_sync = DeltaSync(tenant_id=tenant_id)
        stats = await delta_sync.get_sync_stats()
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sync stats: {str(e)}"
        ) 