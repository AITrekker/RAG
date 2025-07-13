"""
Delta Sync Routes - Use proper SyncService for file discovery and processing
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.backend.dependencies import get_current_tenant_dep, get_file_service_dep, get_sync_service_dep
from src.backend.database import get_async_db
from src.backend.models.database import Tenant, File
from src.backend.services.sync_service import SyncService
from src.backend.services.file_service import FileService

router = APIRouter()

class SyncTriggerRequest(BaseModel):
    force_full_sync: bool = False

@router.get("/status")
async def get_sync_status(
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    db: AsyncSession = Depends(get_async_db)
):
    """Get basic sync status"""
    
    # Count files
    result = await db.execute(
        select(File).where(File.tenant_slug == current_tenant.slug)
    )
    files = result.scalars().all()
    total_files = len(files)
    
    return {
        "tenant_id": current_tenant.slug,
        "status": "idle",
        "latest_sync": None,
        "file_status": {
            "pending": total_files,  # All files are pending until we add embedding tracking
            "processing": 0,
            "failed": 0,
            "total": total_files
        }
    }

@router.get("/history")
async def get_sync_history(
    limit: int = 10,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    db: AsyncSession = Depends(get_async_db)
):
    """Get sync history"""
    return {
        "history": [],
        "total": 0
    }

@router.post("/trigger")
async def trigger_sync(
    request: SyncTriggerRequest,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    sync_service: SyncService = Depends(get_sync_service_dep)
):
    """Trigger delta sync using proper SyncService with file discovery"""
    
    try:
        # Use the proper delta sync service that can discover new files
        sync_plan = await sync_service.detect_file_changes(current_tenant.slug)
        
        if sync_plan.total_changes == 0:
            return {
                "message": f"No changes detected for tenant {current_tenant.slug}",
                "status": "completed",
                "files_processed": 0,
                "chunks_created": 0,
                "details": "No new, updated, or deleted files found"
            }
        
        # Execute the sync plan
        sync_operation = await sync_service.execute_sync_plan(sync_plan)
        
        return {
            "message": f"Sync triggered for tenant {current_tenant.slug}",
            "status": "completed",
            "sync_operation_id": str(sync_operation.id),
            "new_files": len(sync_plan.new_files),
            "updated_files": len(sync_plan.updated_files),
            "deleted_files": len(sync_plan.deleted_files),
            "total_changes": sync_plan.total_changes
        }
        
    except Exception as e:
        return {
            "message": f"Sync failed for tenant {current_tenant.slug}",
            "status": "failed",
            "error": str(e),
            "files_processed": 0,
            "chunks_created": 0
        }

@router.post("/detect-changes")
async def detect_changes(
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    db: AsyncSession = Depends(get_async_db)
):
    """Preview changes"""
    
    result = await db.execute(
        select(File).where(File.tenant_slug == current_tenant.slug)
    )
    files = result.scalars().all()
    
    return {
        "changes": {
            "added": [],
            "updated": [{"filename": f.filename, "path": f.file_path} for f in files],
            "deleted": []
        },
        "summary": {
            "total_files": len(files),
            "added_count": 0,
            "updated_count": len(files),
            "deleted_count": 0
        }
    }