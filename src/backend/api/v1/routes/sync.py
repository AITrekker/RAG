"""
Delta Sync API endpoints for the Enterprise RAG Platform.

This module provides endpoints for:
- Delta sync operations with hash tracking
- Sync status and history
- Sync configuration
- Document processing with metadata extraction

All endpoints are scoped to the authenticated tenant.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import hashlib
import os
from pathlib import Path
import logging

from ...models.api_models import (
    SyncTriggerRequest,
    SyncResponse,
    SyncHistoryResponse,
    SyncConfigRequest,
    SyncConfigResponse,
    ErrorResponse
)
from ...core.delta_sync import DeltaSync
from src.backend.middleware.auth import get_current_tenant
from ...config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["Delta Sync"])

# =============================================================================
# DELTA SYNC OPERATIONS
# =============================================================================

@router.post("/trigger", response_model=SyncResponse)
async def trigger_delta_sync(
    request: SyncTriggerRequest,
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Trigger a delta sync operation.
    
    Delta sync:
    1. Scans tenant's document folder
    2. Calculates file hashes
    3. Compares with stored hashes
    4. Only processes changed files (new, modified, deleted)
    5. Extracts metadata and generates embeddings
    6. Updates Qdrant collections
    
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
            progress={"message": "Delta sync queued"}
        )
        
        # Start delta sync operation (async)
        delta_sync = DeltaSync(tenant_id=tenant_id)
        await delta_sync.start_delta_sync(
            sync_id=sync_id,
            force_full_sync=request.force_full_sync,
            document_paths=request.document_paths
        )
        
        return sync_response
        
    except Exception as e:
        logger.error(f"Failed to trigger delta sync: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger delta sync: {str(e)}"
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
        SyncResponse: Sync operation status with detailed progress
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
        logger.error(f"Failed to get sync status: {e}", exc_info=True)
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
        logger.error(f"Failed to get sync history: {e}", exc_info=True)
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
        logger.error(f"Failed to cancel sync: {e}", exc_info=True)
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
        logger.error(f"Failed to get sync config: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sync configuration: {str(e)}"
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
        logger.error(f"Failed to update sync config: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update sync configuration: {str(e)}"
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
        dict: Sync statistics including file counts, processing times, etc.
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Get sync statistics
        delta_sync = DeltaSync(tenant_id=tenant_id)
        stats = await delta_sync.get_sync_stats()
        
        return {
            "tenant_id": tenant_id,
            "total_files": stats.get("total_files", 0),
            "processed_files": stats.get("processed_files", 0),
            "pending_files": stats.get("pending_files", 0),
            "failed_files": stats.get("failed_files", 0),
            "last_sync": stats.get("last_sync"),
            "next_sync": stats.get("next_sync"),
            "sync_duration_avg": stats.get("sync_duration_avg", 0),
            "files_processed_avg": stats.get("files_processed_avg", 0),
            "embedding_count": stats.get("embedding_count", 0),
            "metadata_count": stats.get("metadata_count", 0)
        }
        
    except Exception as e:
        logger.error(f"Failed to get sync stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sync statistics: {str(e)}"
        )

# =============================================================================
# DOCUMENT PROCESSING
# =============================================================================

@router.post("/documents/{file_path:path}/process")
async def process_single_document(
    file_path: str,
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Process a single document manually.
    
    Args:
        file_path: Path to the document relative to tenant's document folder
        current_tenant: Current tenant (from auth)
        
    Returns:
        dict: Processing result
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Process single document
        delta_sync = DeltaSync(tenant_id=tenant_id)
        result = await delta_sync.process_single_document(file_path)
        
        return {
            "file_path": file_path,
            "success": result.success,
            "message": result.message,
            "metadata": result.metadata,
            "embedding_count": result.embedding_count,
            "processing_time": result.processing_time
        }
        
    except Exception as e:
        logger.error(f"Failed to process document {file_path}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {str(e)}"
        )

@router.delete("/documents/{file_path:path}")
async def remove_document(
    file_path: str,
    current_tenant: dict = Depends(get_current_tenant)
):
    """
    Remove a document from Qdrant (does not delete the file).
    
    Args:
        file_path: Path to the document relative to tenant's document folder
        current_tenant: Current tenant (from auth)
        
    Returns:
        dict: Removal result
    """
    try:
        tenant_id = current_tenant["tenant_id"]
        
        # Remove document from Qdrant
        delta_sync = DeltaSync(tenant_id=tenant_id)
        result = await delta_sync.remove_document(file_path)
        
        return {
            "file_path": file_path,
            "success": result.success,
            "message": result.message,
            "removed_embeddings": result.removed_embeddings,
            "removed_metadata": result.removed_metadata
        }
        
    except Exception as e:
        logger.error(f"Failed to remove document {file_path}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove document: {str(e)}"
        ) 