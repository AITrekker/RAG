"""
Simple Sync Routes - Use existing simple_sync function
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.backend.dependencies import get_current_tenant_dep
from src.backend.database import get_async_db
from src.backend.models.database import Tenant, File
from src.backend.services.simple_sync import simple_sync_files

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
        select(File).where(File.tenant_id == current_tenant.id)
    )
    files = result.scalars().all()
    total_files = len(files)
    
    return {
        "tenant_id": str(current_tenant.id),
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
    db: AsyncSession = Depends(get_async_db)
):
    """Trigger sync using existing simple_sync_files function"""
    
    # Use the existing working simple sync function
    result = await simple_sync_files(db, current_tenant.id)
    
    return {
        "message": f"Sync triggered for tenant {current_tenant.slug}",
        "status": result["status"],
        "files_processed": result["files_processed"],
        "chunks_created": result["chunks_created"],
        "details": result["message"]
    }

@router.post("/detect-changes")
async def detect_changes(
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    db: AsyncSession = Depends(get_async_db)
):
    """Preview changes"""
    
    result = await db.execute(
        select(File).where(File.tenant_id == current_tenant.id)
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