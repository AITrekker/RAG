"""
Document synchronization API endpoints for the Enterprise RAG Platform.

Handles document sync operations, status monitoring, and scheduling.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
from enum import Enum
import uuid

from ...core.document_ingestion import DocumentIngestionPipeline
from ...core.embeddings import EmbeddingService
from ...utils.vector_store import VectorStoreManager
from ...utils.file_monitor import FileMonitor
from ...middleware.mock_tenant import get_current_tenant_id
from ...models.database import get_db
from ...core.tenant_manager import TenantManager
from ...models.document import Document
from sqlalchemy.orm import Session
from ...core.delta_sync import DeltaSyncService
from ...core.auditing import get_audit_logger

logger = logging.getLogger(__name__)

router = APIRouter()

# Enums and Models
class SyncStatus(str, Enum):
    """Sync operation status."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncType(str, Enum):
    """Type of sync operation."""
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    AUTO = "auto"


class SyncRequest(BaseModel):
    """Request model for triggering sync operations."""
    sync_type: SyncType = Field(default=SyncType.MANUAL, description="Type of sync operation")
    force_full_sync: Optional[bool] = Field(default=False, description="Force full sync instead of delta")
    include_patterns: Optional[List[str]] = Field(default=None, description="File patterns to include")
    exclude_patterns: Optional[List[str]] = Field(default=None, description="File patterns to exclude")


class DocumentSyncInfo(BaseModel):
    """Information about a synchronized document."""
    filename: str = Field(..., description="Document filename")
    file_path: str = Field(..., description="Full file path")
    file_size: int = Field(..., description="File size in bytes")
    last_modified: datetime = Field(..., description="Last modification timestamp")
    status: str = Field(..., description="Processing status")
    chunks_created: Optional[int] = Field(None, description="Number of chunks created")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class SyncResponse(BaseModel):
    """Response model for sync operations."""
    sync_id: str = Field(..., description="Unique sync operation identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    status: SyncStatus = Field(..., description="Current sync status")
    sync_type: SyncType = Field(..., description="Type of sync operation")
    started_at: datetime = Field(..., description="Sync start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Sync completion timestamp")
    total_files: int = Field(default=0, description="Total number of files to process")
    processed_files: int = Field(default=0, description="Number of files processed")
    successful_files: int = Field(default=0, description="Number of successfully processed files")
    failed_files: int = Field(default=0, description="Number of failed files")
    total_chunks: int = Field(default=0, description="Total number of chunks created")
    processing_time: Optional[float] = Field(None, description="Total processing time")
    error_message: Optional[str] = Field(None, description="Error message if sync failed")
    documents: List[DocumentSyncInfo] = Field(default_factory=list, description="Processed documents")


class SyncHistoryResponse(BaseModel):
    """Response model for sync history."""
    syncs: List[SyncResponse] = Field(default_factory=list, description="List of sync operations")
    total_count: int = Field(..., description="Total number of sync operations")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of syncs per page")


class SyncScheduleResponse(BaseModel):
    """Response model for sync schedule information."""
    tenant_id: str = Field(..., description="Tenant identifier")
    auto_sync_enabled: bool = Field(..., description="Whether auto sync is enabled")
    sync_interval_hours: int = Field(..., description="Sync interval in hours")
    next_scheduled_sync: Optional[datetime] = Field(None, description="Next scheduled sync time")
    last_auto_sync: Optional[datetime] = Field(None, description="Last automatic sync time")


class SyncScheduleUpdateRequest(BaseModel):
    """Request model for updating sync schedule."""
    auto_sync_enabled: bool = Field(..., description="Whether to enable automatic sync")
    sync_interval_hours: int = Field(..., ge=1, le=168, description="Sync interval in hours (1-168)")


# Local dependency functions
def get_embedding_service() -> EmbeddingService:
    """Get embedding service."""
    return EmbeddingService()

def get_vector_store_manager() -> VectorStoreManager:
    """Get vector store manager."""
    return VectorStoreManager()


# Dependencies
async def get_ingestion_pipeline(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    vector_store_manager: VectorStoreManager = Depends(get_vector_store_manager),
    tenant_id: str = Depends(get_current_tenant_id)
) -> DocumentIngestionPipeline:
    """Get document ingestion pipeline for the current tenant."""
    try:
        return DocumentIngestionPipeline(
            embedding_service=embedding_service,
            vector_store_manager=vector_store_manager,
            tenant_id=tenant_id
        )
    except Exception as e:
        logger.error(f"Failed to initialize ingestion pipeline for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize document ingestion service"
        )


@router.post("/sync", response_model=SyncResponse)
async def trigger_sync(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    pipeline: DocumentIngestionPipeline = Depends(get_ingestion_pipeline),
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Trigger a document synchronization operation.
    
    Starts a sync operation to process documents from the tenant's folder.
    The operation runs in the background and can be monitored via the status endpoint.
    """
    try:
        logger.info(f"Triggering sync for tenant {tenant_id}, type: {request.sync_type}")
        
        # Generate sync run ID
        sync_run_id = f"sync-{uuid.uuid4()}"
        
        # Create initial sync response
        sync_response = SyncResponse(
            sync_id=sync_run_id,
            tenant_id=tenant_id,
            status=SyncStatus.RUNNING,
            sync_type=request.sync_type,
            started_at=datetime.utcnow()
        )
        
        # Add background task for actual sync processing
        background_tasks.add_task(
            process_sync_operation,
            sync_run_id=sync_run_id,
            tenant_id=tenant_id,
            pipeline=pipeline,
            db=next(get_db())
        )
        
        logger.info(f"Sync operation {sync_run_id} started for tenant {tenant_id}")
        return sync_response
        
    except Exception as e:
        logger.error(f"Failed to trigger sync for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger sync operation: {str(e)}"
        )


async def process_sync_operation(
    sync_run_id: str,
    tenant_id: str,
    pipeline: DocumentIngestionPipeline,
    db: Session
):
    """Background task to process sync operation using DeltaSyncService."""
    audit_logger = get_audit_logger()
    audit_logger.log_sync_event(db, sync_run_id, tenant_id, "SYNC_START", "IN_PROGRESS", "Synchronization process started.")
    
    try:
        logger.info(f"Processing delta sync operation {sync_run_id} for tenant {tenant_id}")
        
        # Initialize the delta sync service
        delta_sync_service = DeltaSyncService(
            tenant_id=tenant_id,
            db=db,
            ingestion_pipeline=pipeline,
            sync_run_id=sync_run_id,
            audit_logger=audit_logger
        )

        # Run the synchronization
        delta_sync_service.run_sync()

        logger.info(f"Sync operation {sync_run_id} completed successfully")
        audit_logger.log_sync_event(db, sync_run_id, tenant_id, "SYNC_END", "SUCCESS", "Synchronization process finished successfully.")

    except Exception as e:
        error_message = f"Synchronization failed: {str(e)}"
        logger.error(f"Sync operation {sync_run_id} failed: {e}", exc_info=True)
        audit_logger.log_sync_event(db, sync_run_id, tenant_id, "SYNC_END", "FAILURE", error_message, metadata={"error": str(e)})
        # TODO: Update main sync status in DB
    finally:
        db.close()


@router.get("/sync/status", response_model=SyncResponse)
async def get_current_sync_status(
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get the status of the current or most recent sync operation.
    
    Returns information about the current sync operation or the last completed one.
    """
    try:
        logger.info(f"Getting sync status for tenant {tenant_id}")
        
        # TODO: Implement actual sync status retrieval from database
        # For now, return mock data
        
        mock_response = SyncResponse(
            sync_id=f"{tenant_id}-{int(datetime.utcnow().timestamp() * 1000)}",
            tenant_id=tenant_id,
            status=SyncStatus.COMPLETED,
            sync_type=SyncType.SCHEDULED,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            total_files=25,
            processed_files=25,
            successful_files=23,
            failed_files=2,
            total_chunks=156,
            processing_time=45.2
        )
        
        return mock_response
        
    except Exception as e:
        logger.error(f"Failed to get sync status for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve sync status"
        )


@router.get("/sync/{sync_id}", response_model=SyncResponse)
async def get_sync_operation(
    sync_id: str,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get detailed information about a specific sync operation.
    
    Returns comprehensive information about the sync operation including
    processed documents and any errors.
    """
    try:
        logger.info(f"Getting sync operation {sync_id} for tenant {tenant_id}")
        
        # Validate sync ID format
        if not sync_id.startswith(tenant_id):
            raise HTTPException(
                status_code=404,
                detail="Sync operation not found"
            )
        
        # TODO: Implement actual sync operation retrieval from database
        # For now, return mock data
        
        mock_documents = [
            DocumentSyncInfo(
                filename="employee-handbook.pdf",
                file_path="/tenant-docs/employee-handbook.pdf",
                file_size=1024000,
                last_modified=datetime.utcnow(),
                status="completed",
                chunks_created=15,
                processing_time=2.3
            ),
            DocumentSyncInfo(
                filename="policies.docx",
                file_path="/tenant-docs/policies.docx",
                file_size=512000,
                last_modified=datetime.utcnow(),
                status="failed",
                error_message="Unsupported document format"
            )
        ]
        
        mock_response = SyncResponse(
            sync_id=sync_id,
            tenant_id=tenant_id,
            status=SyncStatus.COMPLETED,
            sync_type=SyncType.MANUAL,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            total_files=2,
            processed_files=2,
            successful_files=1,
            failed_files=1,
            total_chunks=15,
            processing_time=2.3,
            documents=mock_documents
        )
        
        return mock_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sync operation {sync_id} for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve sync operation"
        )


@router.get("/sync/history", response_model=SyncHistoryResponse)
async def get_sync_history(
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[SyncStatus] = None,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get sync operation history for the current tenant.
    
    Returns paginated list of sync operations with optional status filtering.
    """
    try:
        logger.info(f"Getting sync history for tenant {tenant_id}, page {page}")
        
        # TODO: Implement actual sync history retrieval from database
        # For now, return mock data
        
        mock_syncs = [
            SyncResponse(
                sync_id=f"{tenant_id}-{i}",
                tenant_id=tenant_id,
                status=SyncStatus.COMPLETED,
                sync_type=SyncType.SCHEDULED if i % 2 == 0 else SyncType.MANUAL,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                total_files=20 + i,
                processed_files=20 + i,
                successful_files=18 + i,
                failed_files=2,
                total_chunks=100 + i * 10,
                processing_time=30.0 + i
            )
            for i in range(1, 6)
        ]
        
        # Apply status filter if provided
        if status_filter:
            mock_syncs = [sync for sync in mock_syncs if sync.status == status_filter]
        
        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_syncs = mock_syncs[start_idx:end_idx]
        
        return SyncHistoryResponse(
            syncs=paginated_syncs,
            total_count=len(mock_syncs),
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"Failed to get sync history for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve sync history"
        )


@router.delete("/sync/{sync_id}")
async def cancel_sync_operation(
    sync_id: str,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Cancel a running sync operation.
    
    Attempts to cancel a sync operation that is currently running.
    """
    try:
        logger.info(f"Cancelling sync operation {sync_id} for tenant {tenant_id}")
        
        # Validate sync ID format
        if not sync_id.startswith(tenant_id):
            raise HTTPException(
                status_code=404,
                detail="Sync operation not found"
            )
        
        # TODO: Implement actual sync cancellation logic
        # This would involve:
        # 1. Finding the running sync operation
        # 2. Stopping the background task
        # 3. Updating the sync status to cancelled
        # 4. Cleaning up any partial processing
        
        return {"message": "Sync operation cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel sync operation {sync_id} for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to cancel sync operation"
        )


@router.get("/sync/schedule", response_model=SyncScheduleResponse)
async def get_sync_schedule(
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Get automatic sync schedule configuration for the current tenant.
    
    Returns information about the automatic sync schedule and next planned sync.
    """
    try:
        logger.info(f"Getting sync schedule for tenant {tenant_id}")
        
        # TODO: Implement actual sync schedule retrieval from tenant settings
        # For now, return mock data
        
        mock_response = SyncScheduleResponse(
            tenant_id=tenant_id,
            auto_sync_enabled=True,
            sync_interval_hours=24,
            next_scheduled_sync=datetime.utcnow(),
            last_auto_sync=datetime.utcnow()
        )
        
        return mock_response
        
    except Exception as e:
        logger.error(f"Failed to get sync schedule for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve sync schedule"
        )


@router.put("/sync/schedule")
async def update_sync_schedule(
    request: SyncScheduleUpdateRequest,
    tenant_id: str = Depends(get_current_tenant_id)
):
    """
    Update automatic sync schedule configuration.
    
    Updates the automatic sync settings for the current tenant.
    """
    try:
        logger.info(f"Updating sync schedule for tenant {tenant_id}: enabled={request.auto_sync_enabled}, interval={request.sync_interval_hours}h")
        
        # TODO: Implement actual sync schedule update in tenant settings
        # This would involve:
        # 1. Updating tenant configuration
        # 2. Rescheduling automatic sync tasks
        # 3. Validating the new schedule
        
        return {
            "message": "Sync schedule updated successfully",
            "auto_sync_enabled": request.auto_sync_enabled,
            "sync_interval_hours": request.sync_interval_hours
        }
        
    except Exception as e:
        logger.error(f"Failed to update sync schedule for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update sync schedule"
        ) 