"""
Simplified Sync API Endpoints
Clean REST API using the new simplified core modules
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.dependencies import get_current_tenant_dep
from src.backend.database import get_async_db
from src.backend.models.database import Tenant
from src.backend.core.sync_coordinator import SyncCoordinator
from src.backend.simple_embedder import (
    get_available_models, 
    get_available_strategies
)

router = APIRouter()


class SyncRequest(BaseModel):
    """Sync request with configuration options"""
    sync_type: str = "delta"  # "delta" or "full"
    embedding_model: Optional[str] = None
    chunking_strategy: Optional[str] = None
    chunk_size: Optional[int] = 512
    chunk_overlap: Optional[int] = 50
    force_reprocess: bool = False


class EmbeddingConfigRequest(BaseModel):
    """Embedding configuration request"""
    model: str
    chunking_strategy: str
    chunk_size: int = 512
    chunk_overlap: int = 50
    max_chunks: int = 1000


@router.get("/models")
async def get_embedding_models():
    """Get available embedding models"""
    return {
        "models": get_available_models(),
        "strategies": get_available_strategies(),
        "default_config": {
            "model": "sentence-transformers/all-MiniLM-L6-v2",
            "chunking_strategy": "fixed-size",
            "chunk_size": 512,
            "chunk_overlap": 50
        }
    }


@router.get("/status")
async def get_sync_status(
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    db: AsyncSession = Depends(get_async_db)
):
    """Get current sync status for tenant"""
    coordinator = SyncCoordinator(db)
    status = await coordinator.get_sync_status(current_tenant.slug)
    return status


@router.post("/trigger")
async def trigger_sync(
    request: SyncRequest = None,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    db: AsyncSession = Depends(get_async_db)
):
    """Trigger sync with configuration options"""
    
    try:
        coordinator = SyncCoordinator(db)
        
        # Default values if no request provided
        if request is None:
            request = SyncRequest()
        
        # Determine sync type
        force_full_sync = (request.sync_type == "full") or request.force_reprocess
        
        # Execute sync
        results = await coordinator.quick_sync(
            tenant_slug=current_tenant.slug,
            force_full_sync=force_full_sync,
            embedding_model=request.embedding_model,
            chunking_strategy=request.chunking_strategy
        )
        
        return {
            "status": "completed",
            "tenant": current_tenant.slug,
            "sync_type": request.sync_type,
            **results
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {str(e)}"
        )


@router.post("/preview")
async def preview_changes(
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    db: AsyncSession = Depends(get_async_db),
    force_full_sync: bool = False
):
    """Preview what changes would be made without executing sync"""
    
    try:
        coordinator = SyncCoordinator(db)
        plan = await coordinator.discover_changes(current_tenant.slug, force_full_sync)
        
        from src.backend.core.document_discovery import get_sync_summary
        summary = get_sync_summary(plan)
        
        return {
            "tenant": current_tenant.slug,
            "preview": True,
            "changes_detected": plan.total_changes,
            "summary": summary,
            "details": {
                "new_files": [{"name": f.name, "size": f.size} for f in plan.new_files],
                "updated_files": [{"name": fs_info.name, "size": fs_info.size} 
                                for _, fs_info in plan.updated_files],
                "deleted_files": [{"name": f.filename, "path": f.file_path} 
                                for f in plan.deleted_files]
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Preview failed: {str(e)}"
        )


@router.post("/configure")
async def configure_embeddings(
    config: EmbeddingConfigRequest,
    current_tenant: Tenant = Depends(get_current_tenant_dep)
):
    """Configure embedding settings (for future syncs)"""
    
    # Validate model and strategy
    available_models = [m["value"] for m in get_available_models()]
    available_strategies = [s["value"] for s in get_available_strategies()]
    
    if config.model not in available_models:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model. Available: {available_models}"
        )
    
    if config.chunking_strategy not in available_strategies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy. Available: {available_strategies}"
        )
    
    # In a real implementation, you might save this to user preferences
    # For now, just return the validated config
    return {
        "tenant": current_tenant.slug,
        "message": "Configuration validated",
        "config": {
            "model": config.model,
            "chunking_strategy": config.chunking_strategy,
            "chunk_size": config.chunk_size,
            "chunk_overlap": config.chunk_overlap,
            "max_chunks": config.max_chunks
        },
        "note": "Use this config in sync requests to apply these settings"
    }


@router.get("/history")
async def get_sync_history(
    limit: int = 10,
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    db: AsyncSession = Depends(get_async_db)
):
    """Get sync history (simplified for now)"""
    
    coordinator = SyncCoordinator(db)
    status = await coordinator.get_sync_status(current_tenant.slug)
    
    # For now, return current status as "history"
    # In a full implementation, you'd track sync operations in the database
    return {
        "tenant": current_tenant.slug,
        "current_status": status,
        "history": [],
        "note": "Full history tracking not yet implemented"
    }


@router.post("/reset-failed")
async def reset_failed_files(
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    db: AsyncSession = Depends(get_async_db)
):
    """Reset failed files to retry them"""
    
    try:
        from src.backend.core.database_operations import reset_failed_files
        
        reset_count = await reset_failed_files(db, current_tenant.slug)
        
        return {
            "tenant": current_tenant.slug,
            "message": f"Reset {reset_count} failed files to pending",
            "files_reset": reset_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Reset failed: {str(e)}"
        )


@router.delete("/cleanup")
async def cleanup_orphaned_data(
    current_tenant: Tenant = Depends(get_current_tenant_dep),
    db: AsyncSession = Depends(get_async_db)
):
    """Clean up orphaned embeddings"""
    
    try:
        from src.backend.core.database_operations import cleanup_orphaned_embeddings
        
        cleaned_count = await cleanup_orphaned_embeddings(db)
        
        return {
            "tenant": current_tenant.slug,
            "message": f"Cleaned up {cleaned_count} orphaned embeddings",
            "embeddings_cleaned": cleaned_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cleanup failed: {str(e)}"
        )