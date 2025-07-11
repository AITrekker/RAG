"""
Sync Management API Routes - Using the enterprise-level sync operations manager
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel

from src.backend.dependencies import (
    get_current_tenant_dep,
    get_sync_service_dep,
    get_db_session
)
from src.backend.services.sync_service import SyncService
# Removed SyncOperationsManager for simplified approach
from src.backend.models.database import Tenant
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def _create_simple_full_sync_plan(sync_service: SyncService, tenant_id: UUID):
    """Create a simple full sync plan that marks all files as updated"""
    from src.backend.services.sync_service import SyncPlan, FileChange, ChangeType
    
    # Get all files from database
    db_files = await sync_service.file_service.list_files(tenant_id, limit=10000)
    
    # Create changes for all files to force reprocessing
    changes = []
    for db_file in db_files:
        changes.append(FileChange(
            change_type=ChangeType.UPDATED,
            file_path=db_file.file_path,
            file_id=db_file.id,
            old_hash=db_file.file_hash,
            new_hash=db_file.file_hash,  # Same hash, but force update
            file_size=db_file.file_size,
            modified_time=db_file.updated_at
        ))
    
    print(f"🔄 SIMPLE FULL SYNC: Force processing {len(changes)} files for tenant {tenant_id}")
    return SyncPlan(tenant_id=tenant_id, changes=changes)


class SyncTriggerRequest(BaseModel):
    force_full_sync: bool = False


# Simplified sync approach - no complex operations manager needed


@router.post("/")
async def create_sync(
    request: Dict[str, Any],
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Create a new sync operation (simplified)"""
    try:
        force_full = request.get("force_full_sync", False)
        
        if force_full:
            sync_plan = await _create_simple_full_sync_plan(sync_service, current_tenant.id)
        else:
            sync_plan = await sync_service.detect_file_changes(current_tenant.id)
        
        if sync_plan.total_changes == 0:
            return {
                "status": "completed",
                "message": "No changes detected",
                "total_files": 0,
                "files_processed": 0
            }
        
        sync_op = await sync_service.execute_sync_plan(sync_plan, triggered_by=None)
        
        return {
            "status": "completed",
            "sync_id": str(sync_op.id),
            "message": "Sync completed successfully",
            "total_files": sync_plan.total_changes,
            "files_processed": sync_plan.total_changes
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create sync: {str(e)}"
        )


@router.post("/trigger")
async def trigger_sync(
    request: SyncTriggerRequest,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Trigger a sync operation (simplified)"""
    try:
        print(f"🚀 Triggering simplified sync for tenant {current_tenant.id}")
        
        if request.force_full_sync:
            # Force full sync - create a sync plan that processes all files
            sync_plan = await _create_simple_full_sync_plan(sync_service, current_tenant.id)
        else:
            # Regular delta sync
            sync_plan = await sync_service.detect_file_changes(current_tenant.id)
        
        print(f"📋 Sync plan: {len(sync_plan.new_files)} new, {len(sync_plan.updated_files)} updated, {len(sync_plan.deleted_files)} deleted")
        
        if sync_plan.total_changes == 0:
            return {
                "status": "completed",
                "message": "No changes detected",
                "total_files": 0,
                "files_processed": 0
            }
        
        # Execute sync plan directly
        sync_op = await sync_service.execute_sync_plan(sync_plan, triggered_by=None)
        
        return {
            "status": "completed",
            "sync_id": str(sync_op.id),
            "message": "Sync completed successfully",
            "total_files": sync_plan.total_changes,
            "files_processed": sync_plan.total_changes
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger sync: {str(e)}"
        )


@router.get("/status")
async def get_sync_status(
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Get comprehensive sync status for the authenticated tenant (simplified)"""
    try:
        status_info = await sync_service.get_sync_status(current_tenant.id)
        return status_info
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync status: {str(e)}"
        )


@router.get("/history")
async def get_sync_history(
    limit: int = 50,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Get sync history for the authenticated tenant"""
    try:
        operations = await sync_service.get_sync_history(
            tenant_id=current_tenant.id,
            limit=limit
        )
        
        history = [
            {
                "id": str(op.id),
                "operation_type": op.operation_type,
                "status": op.status,
                "started_at": op.started_at.isoformat(),
                "completed_at": op.completed_at.isoformat() if op.completed_at else None,
                "files_processed": op.files_processed,
                "files_added": op.files_added,
                "files_updated": op.files_updated,
                "files_deleted": op.files_deleted,
                "chunks_created": op.chunks_created or 0,
                "chunks_updated": op.chunks_updated or 0,
                "chunks_deleted": op.chunks_deleted or 0,
                "error_message": op.error_message
            }
            for op in operations
        ]
        
        return {"history": history}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync history: {str(e)}"
        )


@router.get("/{sync_id}")
async def get_sync(
    sync_id: str,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Get specific sync operation status - NOT IMPLEMENTED"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Individual sync operation tracking not yet implemented",
            "planned_features": [
                "Sync operation details",
                "Progress tracking",
                "Error reporting"
            ],
            "status": "planned"
        }
    )


@router.delete("/{sync_id}")
async def delete_sync(
    sync_id: str,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Cancel a sync operation - NOT IMPLEMENTED"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Sync cancellation not yet implemented",
            "planned_features": [
                "Running sync cancellation",
                "Sync operation cleanup",
                "Cancellation confirmation"
            ],
            "status": "planned"
        }
    )


@router.post("/cleanup")
async def cleanup_stuck_syncs(
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Manually trigger cleanup of stuck sync operations (simplified - no background tasks to clean)"""
    try:
        return {
            "message": "No cleanup needed - simplified sync system has no background tasks",
            "operations_cleaned": 0,
            "status": "success"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup stuck syncs: {str(e)}"
        )


@router.post("/detect-changes")
async def detect_changes(
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Detect file changes without executing sync"""
    try:
        sync_plan = await sync_service.detect_file_changes(current_tenant.id)
        
        changes = [
            {
                "change_type": change.change_type.value,
                "file_path": change.file_path,
                "file_id": str(change.file_id) if change.file_id else None,
                "old_hash": change.old_hash,
                "new_hash": change.new_hash,
                "file_size": change.file_size
            }
            for change in sync_plan.changes
        ]
        
        return {
            "total_changes": sync_plan.total_changes,
            "new_files": len(sync_plan.new_files),
            "updated_files": len(sync_plan.updated_files),
            "deleted_files": len(sync_plan.deleted_files),
            "changes": changes
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to detect changes: {str(e)}"
        )


@router.get("/config")
async def get_sync_config(
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Get sync configuration - NOT IMPLEMENTED"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Sync configuration not yet implemented",
            "planned_features": [
                "Per-tenant sync settings",
                "File type filters",
                "Sync intervals",
                "Auto-sync configuration"
            ],
            "status": "planned"
        }
    )


@router.put("/config")
async def update_sync_config(
    config: Dict[str, Any],
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Update sync configuration - NOT IMPLEMENTED"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Sync configuration updates not yet implemented",
            "planned_features": [
                "Configuration validation",
                "Settings persistence",
                "Configuration history"
            ],
            "status": "planned"
        }
    )


@router.get("/stats")
async def get_sync_stats(
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Get sync statistics - NOT IMPLEMENTED"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Sync statistics not yet implemented",
            "planned_features": [
                "Sync performance metrics",
                "File processing statistics",
                "Error rate tracking",
                "Sync frequency analysis"
            ],
            "status": "planned"
        }
    )


@router.post("/documents")
async def create_document_processing(
    request: Dict[str, Any],
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Create document processing job - NOT IMPLEMENTED"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Document-specific sync operations not yet implemented",
            "planned_features": [
                "Individual document processing",
                "Document sync tracking",
                "Processing queue management"
            ],
            "status": "planned"
        }
    )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Delete document and sync - NOT IMPLEMENTED"""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "message": "Document deletion sync not yet implemented",
            "planned_features": [
                "Document removal from vector store",
                "Embedding cleanup",
                "Sync history tracking"
            ],
            "status": "planned"
        }
    )